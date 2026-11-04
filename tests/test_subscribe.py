#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import io
from test_base import *
from application.back_end.db_models import *
from recipe_helper import GenerateRecipeSource

class SubscribeTestCase(BaseTestCase):
    login_required = 'admin'

    def setUp(self):
        super().setUp()
        #测试数据库跨次运行会保留数据，先清理本模块用到的数据，保证用例可重复运行
        Recipe.delete().execute()
        BookedRecipe.delete().execute()
        LastDelivered.delete().execute()

    def test_my_page(self):
        resp = self.client.get('/my')
        self.assertEqual(resp.status_code, 200)
        data = resp.text
        self.assertTrue(('Custom RSS' in data) and ('Subscribed' in data))

    def test_web_custom_rss(self):
        resp = self.client.post('/my', data={'rss_title': 'bbc', 'url': '', 'fulltext': False})
        self.assertEqual(resp.status_code, 302)
        
        resp = self.client.post('/my', data={'rss_title': 'bbc', 'url': 'www.g.com', 'fulltext': False}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        data = resp.text
        self.assertTrue(('bbc' in data) and ('www.g.com' in data))

    def test_ajax_custom_rss(self):
        data = {'title': 'bbc', 'url': 'www.gg.com', 'fulltext': False, 'recipeId': '', 'fromsharedlibrary': ''}
        resp = self.client.post('/customrss/add', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        self.assertEqual(resp.json['url'], 'https://www.gg.com')
        bbc_id = resp.json['id']
        self.assertIsNotNone(bbc_id)

        data = {'title': 'bbc', 'url': 'www.gg.com', 'fulltext': False, 'recipeId': '', 'fromsharedlibrary': '1'}
        resp = self.client.post('/customrss/add', data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'Duplicated subscription!')

        data = {'title': 'bbc', 'url': 'www.gg.com', 'fulltext': False, 'recipeId': '', 'fromsharedlibrary': '1'}
        resp = self.client.post('/customrss/add', data=data)
        self.assertEqual(resp.status_code, 200)

        data = {'title': 'bbc', 'url': '', 'fulltext': False, 'recipeId': 'builtin:am730', 'fromsharedlibrary': ''}
        resp = self.client.post('/customrss/add', data=data)
        self.assertEqual(resp.status_code, 200)
        #depends if local server is executing or not
        self.assertTrue(resp.json['status'] in ['The recipe does not exist.', 'Failed to fetch the recipe.'])

        resp = self.client.post('/customrss/delete', data={'id': bbc_id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')

        resp = self.client.post('/customrss/delete', data={'id': bbc_id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'The Rss does not exist.')

    def test_ajax_recipe(self):
        resp = self.client.post('/recipe/subscribe', data={'id': 'builtin:111am730', 'separated': False})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'The recipe does not exist.')
        resp = self.client.post('/recipe/subscribe', data={'id': 'upload:111am730', 'separated': False})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'The recipe does not exist.')
        
        resp = self.client.post('/recipe/subscribe', data={'id': 'builtin:am730', 'separated': False})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        self.assertEqual(resp.json['title'], 'AM730')
        recipe = BookedRecipe.get_or_none(BookedRecipe.recipe_id=='builtin:am730')
        self.assertEqual(recipe.title, 'AM730')

        resp = self.client.post('/recipe/subscribe', data={'id': 'builtin:am730', 'separated': True})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        self.assertEqual(resp.json['title'], 'AM730')
        recipe = BookedRecipe.get_or_none(BookedRecipe.recipe_id=='builtin:am730')
        self.assertEqual(recipe.separated, True)

        resp = self.client.post('/recipe/schedule', data={'id': 'builtin:am730', 'type': 'weekday', 'days': '2,3', 'times': '5,15'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        self.assertEqual(resp.json['send_days'], {'type': 'weekday', 'days': [2, 3]})
        self.assertEqual(resp.json['send_times'], [5, 15])
        recipe = BookedRecipe.get_or_none(BookedRecipe.recipe_id=='builtin:am730')
        self.assertEqual(recipe.send_days, {'type': 'weekday', 'days': [2, 3]})
        self.assertEqual(recipe.send_times, [5, 15])

        resp = self.client.post('/recipe/unsubscribe', data={'id': 'builtin:am730'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        self.assertEqual(resp.json['title'], 'AM730')
        recipe = BookedRecipe.get_or_none(BookedRecipe.recipe_id=='builtin:am730')
        self.assertEqual(recipe, None)

        resp = self.client.post('/recipe/schedule', data={'id': 'builtin:am730', 'Wednesday': 1, 'Thursday': 1, '5': 1, '15': 1})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'This recipe has not been subscribed to yet.')
        
        resp = self.client.post('/recipe/delete', data={'id': 'builtin:am730'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'You can only delete the uploaded recipe.')
        
        resp = self.client.post('/recipe/unknown', data={'id': 'builtin:am730'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'Unknown command: unknown')

    def test_upload_recipe(self):
        data = {'file': (io.BytesIO(b'sldfsdfjlksx'), 'test.recipe')}
        resp = self.client.post('/recipe/upload', data=data, follow_redirects=True, content_type='multipart/form-data')
        self.assertIn('Can not read uploaded file, Error:', resp.json['status'])

        data = {'recipe_file': (io.BytesIO('非法'.encode('gbk')), 'test.recipe')}
        resp = self.client.post('/recipe/upload', data=data, follow_redirects=True, content_type='multipart/form-data')
        self.assertIn('Failed to decode the recipe.', resp.json['status'])

        data = {'recipe_file': (io.BytesIO(b'dfljdflsdjfljsdfdsfdf'), 'test.recipe')}
        resp = self.client.post('/recipe/upload', data=data, follow_redirects=True, content_type='multipart/form-data')
        self.assertIn('Failed to save the recipe.', resp.json['status'])

        feeds = ['http://www.g.com', 'https://www.x.com']
        user = KeUser.get_or_none(KeUser.name == 'admin')
        src = GenerateRecipeSource('mytest', feeds, user)
        data = {'recipe_file': (io.BytesIO(src.encode('utf-8')), 'test.recipe')}
        resp = self.client.post('/recipe/upload', data=data, follow_redirects=True, content_type='multipart/form-data')
        self.assertEqual(resp.json['status'], 'ok')
        self.assertEqual(resp.json['title'], 'mytest')
        upload_id = resp.json['id']
        self.assertIsNotNone(upload_id)

        resp = self.client.get('/viewsrc/{}'.format(upload_id.replace(':', '__')))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('class UserRecipe', resp.text)

        resp = self.client.post('/recipe/delete', data={'id': upload_id})
        self.assertEqual(resp.json['status'], 'ok')
    
    def test_recipe_login_info(self):
        resp = self.client.post('/recipelogininfo', data={'id': 'builtin:am730', 'account': '', 'password': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'The recipe does not exist.')

        resp = self.client.post('/recipe/subscribe', data={'id': 'builtin:am730', 'separated': False})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        
        resp = self.client.post('/recipelogininfo', data={'id': 'builtin:am730', 'account': '1', 'password': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
        
        resp = self.client.post('/recipelogininfo', data={'id': 'builtin:am730', 'account': '', 'password': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json['status'], 'ok')
    
    def test_recipe_viewsrc(self):
        resp = self.client.get('/viewsrc/builtin__am730')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('class AM730(BasicNewsRecipe):', resp.text)

    def test_summarizer_custom_model_and_endpoint(self):
        from simple_ai_provider import SimpleAiProvider, AI_LIST
        self.assertIn('deepseek', AI_LIST)
        self.assertEqual(AI_LIST['deepseek']['models'][0]['name'], 'deepseek-flash')
        self.assertEqual(SimpleAiProvider.build_api_url('https://api.deepseek.com'), 'https://api.deepseek.com/v1/chat/completions')
        self.assertEqual(SimpleAiProvider.build_api_url('https://api.siliconflow.cn/v1'), 'https://api.siliconflow.cn/v1/chat/completions')
        self.assertEqual(SimpleAiProvider.build_api_url('https://api.perplexity.ai/chat/completions'), 'https://api.perplexity.ai/chat/completions')
        self.assertEqual(SimpleAiProvider.build_api_url('https://xxx.openai.azure.com/openai/deployments/{model}/chat/completions?api-version=2024-02-15', model='gpt-4o'), 'https://xxx.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-02-15')

        user = KeUser.get_or_none(KeUser.name == 'admin')
        recipe = Recipe.create(user=user, title='TestRecipe', type_='custom', url='https://test.com', is_active=True)
        resp = self.client.get(f'/summarizer/custom__{recipe.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('summarizer_custom_model', resp.text)
        self.assertIn('Endpoint', resp.text)

        post_data = {
            'enable': '1', 'engine': 'openai', 'model': '__custom__', 'custom_model': 'deepseek-chat',
            'api_host': 'https://api.deepseek.com', 'api_key': 'sk-test'
        }
        resp = self.client.post(f'/summarizer/custom__{recipe.id}', data=post_data)
        self.assertEqual(resp.status_code, 200)
        saved_recipe = Recipe.get_by_id(recipe.id)
        self.assertEqual(saved_recipe.summarizer.get('model'), 'deepseek-chat')
        self.assertEqual(saved_recipe.summarizer.get('api_host'), 'https://api.deepseek.com')
