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
        recipe = Recipe.create(user=user.name, title='TestRecipe', type_='custom', url='https://test.com', is_active=True)
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

    def test_cross_user_isolation(self):
        from application.view.login import CreateAccountIfNotExist
        with self.app.app_context():
            CreateAccountIfNotExist('alice', 'alice123')
            CreateAccountIfNotExist('bob', 'bob123')
        user_alice = KeUser.get_or_none(KeUser.name == 'alice')
        user_bob = KeUser.get_or_none(KeUser.name == 'bob')

        alice_rss = Recipe.create(user='alice', title='AliceRSS', type_='custom', url='https://alice.com')
        alice_recipe = Recipe.create(user='alice', title='AliceRecipe', type_='upload', src='ALICE_SECRET_CODE')
        alice_booked = BookedRecipe.create(user='alice', recipe_id='builtin:economist', title='The Economist', 
            description='Economic news', account='alice_acc', password='alice_pwd', separated=False)

        # Log in as bob (ordinary user)
        self.client.post('/login', data={'username': 'bob', 'password': 'bob123'})

        # 1. Bob attempts to view Alice's uploaded recipe source
        resp = self.client.get(f'/viewsrc/upload__{alice_recipe.id}')
        self.assertNotIn('ALICE_SECRET_CODE', resp.text)
        self.assertIn('The recipe does not exist', resp.text)

        # 2. Bob attempts to delete Alice's custom RSS
        resp = self.client.post('/customrss/delete', data={'id': f'custom:{alice_rss.id}'})
        self.assertIn('does not exist', resp.json.get('status', ''))
        self.assertIsNotNone(Recipe.get_by_id_or_none(alice_rss.id))

        # 3. Bob attempts to delete Alice's uploaded recipe
        resp = self.client.post('/recipe/delete', data={'id': f'upload:{alice_recipe.id}', 'force': '1'})
        self.assertIn('does not exist', resp.json.get('status', ''))
        self.assertIsNotNone(Recipe.get_by_id_or_none(alice_recipe.id))

        # 4. Bob attempts to subscribe to Alice's uploaded recipe
        resp = self.client.post('/recipe/subscribe', data={'id': f'upload:{alice_recipe.id}'})
        self.assertIn('does not exist', resp.json.get('status', ''))

        # 5. Bob attempts to overwrite Alice's recipe login info
        resp = self.client.post('/recipelogininfo', data={'id': 'builtin:economist', 'account': 'bob_acc', 'password': 'bob_pwd'})
        refreshed_alice_booked = BookedRecipe.get_by_id(alice_booked.id)
        self.assertEqual(refreshed_alice_booked.account, 'alice_acc')

        # 6. Bob attempts to share Alice's recipe to shared library
        resp = self.client.post('/library', data={'id': f'upload:{alice_recipe.id}', 'category': 'News'})
        self.assertIn('does not exist', resp.json.get('status', ''))

        # 7. Bob attempts to modify Alice's custom RSS translator settings
        resp = self.client.post(f'/translator/custom__{alice_rss.id}', data={'engine': 'google'})
        self.assertIn('The recipe does not exist', resp.text)

        # Clean up
        alice_rss.delete_instance()
        alice_recipe.delete_instance()
        alice_booked.delete_instance()
        user_alice.delete_instance()
        user_bob.delete_instance()
        self.client.post('/login', data={'username': 'admin', 'password': 'admin'})

    def test_recipe_upload_permission(self):
        from application.view.login import CreateAccountIfNotExist
        # 创建普通用户 testuser
        KeUser.delete().where(KeUser.name == 'testuser').execute()
        with self.app.app_context():
            CreateAccountIfNotExist('testuser', 'testuser123', 'test@example.com', allow_recipe_upload=False)
        user_test = KeUser.get_or_none(KeUser.name == 'testuser')
        self.assertIsNotNone(user_test)
        self.assertFalse(user_test.can_upload_recipe())

        # 切换到普通用户登录
        self.client.post('/login', data={'username': 'testuser', 'password': 'testuser123'})

        # 尝试上传 recipe，应当被权限拦截
        feeds = ['http://www.g.com']
        src = GenerateRecipeSource('non_admin_test', feeds, user_test)
        data = {'recipe_file': (io.BytesIO(src.encode('utf-8')), 'test.recipe')}
        resp = self.client.post('/recipe/upload', data=data, follow_redirects=True, content_type='multipart/form-data')
        self.assertEqual(resp.json.get('status'), 'You do not have sufficient privileges.')

        # 管理员为 testuser 开启上传权限
        user_test.set_cfg('allow_recipe_upload', True)
        user_test.save()

        # 重新上传，此时应当成功
        data = {'recipe_file': (io.BytesIO(src.encode('utf-8')), 'test.recipe')}
        resp = self.client.post('/recipe/upload', data=data, follow_redirects=True, content_type='multipart/form-data')
        self.assertEqual(resp.json.get('status'), 'ok')
        upload_id = resp.json.get('id')
        self.assertIsNotNone(upload_id)

        # 清理
        Recipe.delete().where(Recipe.user == 'testuser').execute()
        user_test.delete_instance()
        self.client.post('/login', data={'username': 'admin', 'password': 'admin'})


