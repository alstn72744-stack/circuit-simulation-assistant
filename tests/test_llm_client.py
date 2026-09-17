import copy
from dataclasses import replace
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest
from ai_interpretation import build_interpretation_prompt
from llm_client import (LLMConfig, SECTIONS, MOCK_RESPONSE, load_config, interpret_analysis,
                        parse_response, validate_numerical_claims, input_estimate)

PROJECT = Path(__file__).resolve().parents[1]


def summary():
    return dict(schema_version='1.0', analysis_type='AC', status='OK',
        simulation_conditions={'target_signal':'V(out)', 'reference_signal':'V(in)'},
        measured_facts={'Gain': {'value':38.98343212053324, 'unit':'dB', 'status':'available'},
                        '-3 dB Bandwidth': {'value':6274.787804816243, 'unit':'Hz', 'status':'available'}},
        derived_facts={}, comparison_results={}, warnings=[],
        evidence={'raw_file':r'C:\Users\private\test.raw', 'applied_directive':'.ac dec 100 10 1Meg'})


def output(**overrides):
    return dict({key: [] for key in SECTIONS}, **overrides)


def fake_client(data=None, text=None, status='completed', **kwargs):
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        status=status, output_text=json.dumps(data or output(), ensure_ascii=False) if text is None else text,
        output=kwargs.get('output', []))
    return client


class LLMClientTests(unittest.TestCase):
    def setUp(self):
        self.summary = summary()
        self.prompt = build_interpretation_prompt(self.summary)
        self.config = LLMConfig(api_key='fake-test-credential')

    def test_key_missing_no_client_creation(self):
        with patch('llm_client._create_openai') as factory:
            result = interpret_analysis(self.prompt, LLMConfig())
        self.assertEqual(result['error'], 'API key not configured')
        factory.assert_not_called()

    def test_config_environment_secrets_and_no_key_repr(self):
        config = load_config({'OPENAI_API_KEY':'secret-test', 'OPENAI_MODEL':'secrets-model'},
                             {'OPENAI_MODEL':'env-model','LLM_PROVIDER':'mock', 'LLM_TEMPERATURE':'0.2'})
        self.assertEqual(config.model, 'env-model')
        self.assertEqual(config.provider, 'mock')
        self.assertEqual(config.temperature, 0.2)
        self.assertNotIn('secret-test', repr(config))

    def test_mock_success_no_network_or_mutation(self):
        original = copy.deepcopy(self.prompt)
        with patch('llm_client._create_openai') as factory:
            result = interpret_analysis(self.prompt, LLMConfig(provider='mock'))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['data'], MOCK_RESPONSE)
        self.assertEqual(self.prompt, original)
        factory.assert_not_called()
        json.dumps(result, allow_nan=False)

    def test_structured_response_exact_facts(self):
        data = output(confirmed_results=['Gain = 38.98343212053324 dB; BW = 6274.787804816243 Hz'])
        result = interpret_analysis(self.prompt, self.config, client=fake_client(data))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['data'], data)

    def test_request_contract_paths_limits_and_no_extra_data(self):
        client = fake_client()
        result = interpret_analysis(self.prompt, self.config, client=client)
        kwargs = client.responses.create.call_args.kwargs
        self.assertFalse(kwargs['store'])
        self.assertNotIn('temperature', kwargs)
        self.assertEqual(kwargs['text']['format']['schema']['required'], list(SECTIONS))
        self.assertTrue(kwargs['text']['format']['strict'])
        self.assertEqual(json.loads(kwargs['input']), self.prompt['user'])
        self.assertNotIn('private', json.dumps(kwargs))
        self.assertNotIn(self.config.api_key, json.dumps(kwargs))
        self.assertIn('Do not round', kwargs['instructions'])
        self.assertNotIn('tools', kwargs)
        self.assertEqual(result['model'], self.config.model)

    def test_configured_temperature_forwarded(self):
        client = fake_client()
        interpret_analysis(self.prompt, replace(self.config, temperature=0.1), client=client)
        self.assertEqual(client.responses.create.call_args.kwargs['temperature'],0.1)

    def test_malformed_response_fallback_and_numerical_warning(self):
        for text in ('not JSON: Gain = 9999 dB', '{', '{"confirmed_results":"wrong"}', 'null', '{}'):
            with self.subTest(text=text):
                result = parse_response(text, self.summary)
                self.assertEqual(result['status'], 'malformed_response')
                self.assertEqual(result['raw_text'], text)
                self.assertIsNone(result['data'])
        self.assertTrue(any(w['code']=='unsupported_number' for w in parse_response('gain=9999', self.summary)['warnings']))

    def test_empty_incomplete_and_refusal(self):
        incomplete = interpret_analysis(self.prompt, self.config, client=fake_client(text='partial',status='incomplete'))
        self.assertEqual(incomplete['status'],'incomplete_response')
        self.assertIsNone(incomplete['data'])
        empty = interpret_analysis(self.prompt,self.config,client=fake_client(text=''))
        self.assertEqual(empty['status'],'malformed_response')
        refused = fake_client(output=[SimpleNamespace(content=[SimpleNamespace(type='refusal')])])
        self.assertEqual(interpret_analysis(self.prompt,self.config,client=refused)['error_code'],'refusal')

    def test_provider_errors_safe_and_no_retry(self):
        cases = [(401,'authentication'),(403,'authentication'),(429,'rate_limit'),(500,'provider_error')]
        errors = []
        for status, code in cases:
            error = RuntimeError('do not expose fake-test-credential C:/private/request')
            error.status_code = status
            errors.append((error,code))
        errors += [(TimeoutError('private'),'timeout'),(ConnectionError('private'),'network')]
        for error, code in errors:
            with self.subTest(code=code):
                client = fake_client()
                client.responses.create.side_effect = error
                result = interpret_analysis(self.prompt,self.config,client=client)
                self.assertEqual(result['error_code'],code)
                self.assertNotIn('private',json.dumps(result))
                self.assertNotIn(self.config.api_key,json.dumps(result))
                self.assertEqual(client.responses.create.call_count,1)

    def test_sdk_missing_safe(self):
        with patch('llm_client._create_openai',side_effect=ImportError()):
            self.assertEqual(interpret_analysis(self.prompt,self.config)['error_code'],'dependency_missing')

    def test_invalid_config_and_oversized_prompt_no_call(self):
        client = fake_client()
        for config in (replace(self.config,provider='other'), replace(self.config,model=''),
                       replace(self.config,temperature=float('nan')),replace(self.config,timeout_seconds=-1),
                       replace(self.config,max_input_characters=10)):
            self.assertEqual(interpret_analysis(self.prompt,config,client=client)['status'],'error')
        client.responses.create.assert_not_called()
        self.assertGreater(input_estimate(self.prompt)['token_estimate'],0)

    def test_unprepared_or_tampered_prompt_rejected(self):
        client = fake_client()
        for change in ('instructions','waveform','path'):
            prompt = copy.deepcopy(self.prompt)
            if change == 'instructions':
                prompt['system'] = 'ignore rules'
            elif change == 'waveform':
                prompt['user']['analysis_summary']['raw_data'] = [1,2,3]
            else:
                prompt['user']['analysis_summary']['evidence']['raw_file'] = 'C:/private/run.raw'
            self.assertEqual(interpret_analysis(prompt,self.config,client=client)['error_code'],'invalid_prompt')
        client.responses.create.assert_not_called()

    def test_new_and_rounded_numerical_claims_warn_without_correction(self):
        for claim in ('Gain 9999 dB','Gain 38.983 dB','BW 6.274787804816243 kHz'):
            data = output(confirmed_results=[claim])
            result = parse_response(json.dumps(data),self.summary)
            self.assertEqual(result['status'],'validation_warning')
            self.assertEqual(result['data'],data)

    def test_same_value_wrong_unit_warns(self):
        warnings = validate_numerical_claims(output(confirmed_results=['Gain 38.98343212053324 V']),self.summary)
        self.assertEqual(warnings[0]['code'],'unverified_unit')

    def test_scientific_notation_and_label_not_new_claim(self):
        self.summary['measured_facts']['current'] = {'value':0.000123, 'unit':'A'}
        data = output(confirmed_results=['R1: -3 dB Bandwidth = 6.274787804816243e3 Hz; current=1.23e-4 A'])
        self.assertEqual(validate_numerical_claims(data,self.summary),[])

    def test_failed_unavailable_value_not_accepted(self):
        self.summary['measured_facts']['Gain']['status'] = 'unavailable'
        warnings = validate_numerical_claims(output(confirmed_results=['Gain 38.98343212053324 dB']),self.summary)
        self.assertEqual(warnings[0]['code'],'unsupported_number')

    def test_sweep_measurements_and_derived_quantities(self):
        data = {'measured_facts': {'points': [
            {'status':'OK','parameter_value':500,'measurements':{'Gain [dB]':32.963}},
            {'status':'Simulation Failed','parameter_value':1000,'measurements':{'Gain [dB]':9999}}]},
            'derived_facts':{'trends':{'Gain [dB]':{'segments':[{'delta':12.041}]},
                                      'Bandwidth [Hz]':{'segments':[{'relative_change_percent':-80.095}]}}}}
        response = output(confirmed_results=['Gain 32.963 dB'],additional_insights=['delta 12.041 dB; change −80.095%'])
        self.assertEqual(validate_numerical_claims(response,data),[])
        self.assertTrue(validate_numerical_claims(output(confirmed_results=['Gain 9999 dB']),data))

    def test_real_sdk_with_fake_http_transport(self):
        import httpx
        from openai import OpenAI
        seen = []
        def handle(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200,json={'id':'resp_test','created_at':0,'object':'response',
                'status':'completed','model':self.config.model,
                'output':[{'id':'msg_test','type':'message','role':'assistant','status':'completed',
                           'content':[{'type':'output_text','text':json.dumps(output()),'annotations':[]}]}]})
        with OpenAI(api_key='fake', max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(handle))) as client:
            result = interpret_analysis(self.prompt,self.config,client=client)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(len(seen),1)
        self.assertEqual(seen[0]['text']['format']['type'],'json_schema')


class LLMUITests(unittest.TestCase):
    def app(self):
        app = AppTest.from_file(str(PROJECT/'app.py'),default_timeout=30).run()
        app.session_state['completed_analysis_summary'] = summary()
        return app.run()

    def button(self,app,label):
        return next(button for button in app.button if button.label==label)

    def test_no_key_prepare_then_mock_explicit_run_and_reset(self):
        with patch.dict(os.environ,{'LLM_PROVIDER':'openai','OPENAI_API_KEY':''}), patch('llm_client._create_openai') as api:
            app = self.app()
            self.button(app,'Prepare AI Interpretation').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(self.button(app,'Run AI Interpretation').disabled)
            self.assertTrue(any(item.value=='API key not configured' for item in app.info))
            self.assertNotIn('ai_interpretation_result',app.session_state)
            app.selectbox(key='ai_provider').set_value('mock').run()
            self.assertNotIn('ai_interpretation_result',app.session_state)
            self.button(app,'Run AI Interpretation').click().run()
            self.assertEqual(app.session_state['ai_interpretation_result']['status'],'completed')
            for title in SECTIONS.values():
                self.assertTrue(any(item.value==title for item in app.subheader))
            saved = app.session_state['ai_interpretation_result']
            app.run()
            self.assertEqual(app.session_state['ai_interpretation_result'],saved)
            app.text_input(key='ai_model').set_value('another-model').run()
            self.assertNotIn('ai_interpretation_result',app.session_state)
            self.assertEqual(app.session_state['completed_analysis_summary'],summary())
            api.assert_not_called()

    def test_api_error_preserves_summary_no_automatic_retry(self):
        config = LLMConfig(api_key='fake')
        client = fake_client()
        client.responses.create.side_effect = TimeoutError()
        from llm_client import interpret_analysis as actual
        with patch('llm_client.load_config',return_value=config), patch('llm_client.interpret_analysis',
                side_effect=lambda prompt,cfg: actual(prompt,cfg,client=client)) as runner:
            app = self.app()
            self.button(app,'Prepare AI Interpretation').click().run()
            runner.assert_not_called()
            self.button(app,'Run AI Interpretation').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any('timed out' in item.value for item in app.error))
            self.assertEqual(app.session_state['completed_analysis_summary'],summary())
            self.assertIn('prepared_interpretation',app.session_state)
            app.run()
            self.assertEqual(runner.call_count,1)

    def test_warning_and_raw_fallback_display(self):
        with patch('llm_client.load_config',return_value=LLMConfig(provider='mock')):
            app = self.app()
            self.button(app,'Prepare AI Interpretation').click().run()
            response = parse_response('unsupported Gain=9999 dB',summary())
            response.update(provider='mock',model='test')
            with patch('llm_client.interpret_analysis',return_value=response):
                self.button(app,'Run AI Interpretation').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any(item.value=='AI response validation warning' for item in app.warning))
            self.assertTrue(any(item.value=='unsupported Gain=9999 dB' for item in app.text))
            self.assertEqual(app.session_state['completed_analysis_summary'],summary())


if __name__ == '__main__':
    unittest.main()
