import pytest
import json
import yaml

from django.urls import reverse
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.contrib.auth import authenticate
from django.db.models import Q, Sum, F
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from model_bakery import baker
from backend.models import User, ConfirmEmailToken, Category, Shop, Contact, Order, Product, ProductInfo, OrderItem, Parameter, ProductParameter
from unittest.mock import patch

from backend.serializers import ProductInfoSerializer


@pytest.mark.django_db(transaction=True)
class TestRegisterAccount:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('backend:user-register')

    def test_register_success(self):
        # Arrange
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'password': 'SuperSecret123!',
            'company': 'CompanyX',
            'position': 'Developer',
        }

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True
        assert User.objects.filter(email=data['email']).exists()

    def test_register_missing_fields(self):
        # Arrange
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            # Пропущены поля password, company, и position
        }

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is False
        assert 'Errors' in response.json()

    def test_register_invalid_password(self):
        # Arrange
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'password': '123',  # Пароль слишком простой
            'company': 'CompanyX',
            'position': 'Developer',
        }

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is False
        assert 'password' in response.json()['Errors']

    def test_register_duplicate_email(self):
        # Arrange
        existing_user = baker.make(User, email='john.doe@example.com')
        data = {
            'first_name': 'Jane',
            'last_name': 'Doe',
            'email': existing_user.email,
            'password': 'AnotherSuperSecret123!',
            'company': 'CompanyY',
            'position': 'Manager',
        }

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is False
        assert 'email' in response.json()['Errors']


@pytest.mark.django_db(transaction=True)
class TestConfirmAccount:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('backend:user-register-confirm')

    def post(self, request):
        # Arrange
        email = request.data.get('email')
        token_key = request.data.get('token')
        # Act
        user = get_object_or_404(User, email=email)
        token = get_object_or_404(ConfirmEmailToken, user=user, key=token_key)
        
        if not user.is_active:
            user.is_active = True
            user.save()

            token.delete()
            # Assert
            return Response({'Status': True}, status=status.HTTP_200_OK)
        else:
            return Response({'Status': False, 'Message': 'User is already active'}, status=status.HTTP_400_BAD_REQUEST)


        


    def test_confirm_account_invalid_token(self):
        # Arrange
        user = baker.make(User, email='john.doe@example.com', is_active=False)
        baker.make(ConfirmEmailToken, user=user)

        data = {
            'email': user.email,
            'token': 'invalid_token'
        }

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is False
        assert 'Errors' in response.json()

    def test_confirm_account_missing_fields(self):
        # Arrange
        data = {
            'email': 'john.doe@example.com',
            # Пропущен token
        }

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is False
        assert 'Errors' in response.json()


@pytest.mark.django_db(transaction=True)
class TestAccountDetails:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('backend:user-details')
        self.user = baker.make(User, email='john.doe@example.com')
    
    def authenticate_user(self):
        self.client.force_authenticate(user=self.user)

    def test_get_account_details_authenticated(self):
        # Arrange
        self.authenticate_user()

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 200
        assert response.json()['email'] == self.user.email

    def test_get_account_details_unauthenticated(self):
        # Arrange - без аутентификации

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'

    def test_post_update_account_details(self):
        # Arrange
        self.authenticate_user()
        data = {
            'first_name': 'Jane',
            'last_name': 'Doe',
            'password': 'NewStrongPassword123!'
        }

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True

        self.user.refresh_from_db()
        assert self.user.first_name == 'Jane'
        assert self.user.check_password('NewStrongPassword123!')

    def test_post_update_account_details_invalid_password(self):
        # Arrange
        self.authenticate_user()
        data = {
            'password': '123'  # Неподходящий пароль
        }

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is False
        assert 'password' in response.json()['Errors']

    def test_post_update_account_details_unauthenticated(self):
        # Arrange - без аутентификации
        data = {
            'first_name': 'Jane'
        }

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'


@pytest.mark.django_db(transaction=True)
class TestLoginAccount:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('backend:user-login')

    def test_login_invalid_credentials(self):
        # Arrange
        user = baker.make(User, email='john.doe@example.com')
        user.set_password('password123')
        user.save()

        data = {
            'email': 'john.doe@example.com',
            'password': 'wrongpassword'
        }

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is False
        assert response.json()['Errors'] == 'Не удалось авторизовать'

    def test_login_missing_fields(self):
        # Arrange
        data = {
            'email': 'john.doe@example.com'
            # Пропущен пароль
        }

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is False
        assert response.json()['Errors'] == 'Не указаны все необходимые аргументы'



@pytest.mark.django_db(transaction=True)
class TestShopView:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('backend:shops')  

    def test_get_no_active_shops(self):
        # Arrange
        baker.make(Shop, state=False, _quantity=2)  # Только неактивные магазины

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 200
        assert len(response.json()) == 0


@pytest.mark.django_db
class TestChangeUserType:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('backend:user-change-type') 

    def authenticate_user(self, user_type, email='shopuser@example.com', password='password123'):
        user = baker.make('backend.User', email=email, type=user_type, is_active=True) 
        user.set_password(password)
        user.save()

        # Выполняем запрос для получения токена
        login_url = reverse('backend:user-login')
        response = self.client.post(login_url, {'email': email, 'password': password})

        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.content}")

        # Убеждаемся, что получили токен
        assert response.status_code == 200
        token = response.json().get('Token')
        assert token is not None, "Token is None. Authentication failed."

        # Устанавливаем токен для последующих запросов
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        return user

    def test_change_user_type_to_shop(self):
        # Arrange
        password = 'password123'  
        user = self.authenticate_user('buyer', password=password)
        data = {'password': password}  # Используйте тот же пароль здесь

        # Act
        response = self.client.post(self.url, data, format='json')

        # Отладка
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.json()}")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json().get('Status') is True
        assert response.json().get('Message') == 'User type updated to shop'
        
        user.refresh_from_db()
        assert user.type == 'shop'

    def test_change_user_type_to_buyer(self):
        # Arrange
        user = self.authenticate_user('shop')  # Используем метод для создания и аутентификации пользователя
        data = {'password': 'password123'}

        # Act
        response = self.client.post(self.url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True
        assert response.json()['Message'] == 'User type updated to buyer'
        
        user.refresh_from_db()
        assert user.type == 'buyer'

    def test_change_user_type_invalid_password(self):
        # Arrange
        user = baker.make(User, type='buyer')
        user.set_password('password123')
        user.save()
        self.client.force_authenticate(user=user)

        data = {'password': 'wrongpassword'}

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 400
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Incorrect password'


    def test_change_user_type_no_password(self):
        # Arrange
        user = baker.make(User, type='buyer')
        self.client.force_authenticate(user=user)

        data = {}

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 400
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Password is required'

    def test_change_user_type_not_authenticated(self):
        # Arrange
        data = {'password': 'password123'}

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'


@pytest.mark.django_db
class TestContactView:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('backend:user-contact')

    def test_get_contacts_authenticated(self):
        # Arrange
        user = baker.make(User)
        self.client.force_authenticate(user=user)
        baker.make(Contact, user=user, _quantity=3)

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 200
        assert len(response.data) == 3

    def test_get_contacts_unauthenticated(self):
        # Arrange
        # No authenticated user

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'

    def test_post_contact_authenticated(self):
        # Arrange
        user = baker.make(User)
        self.client.force_authenticate(user=user)
        data = {'city': 'City', 'street': 'Street', 'phone': '1234567890'}

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True
        assert Contact.objects.filter(user=user).count() == 1

    def test_post_contact_unauthenticated(self):
        # Arrange
        data = {'city': 'City', 'street': 'Street', 'phone': '1234567890'}

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'

    def test_delete_contact_authenticated(self):
        # Arrange
        user = baker.make(User)
        contact = baker.make(Contact, user=user)
        self.client.force_authenticate(user=user)
        data = {'items': str(contact.id)}

        # Act
        response = self.client.delete(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True
        assert Contact.objects.filter(user=user).count() == 0

    def test_delete_contact_unauthenticated(self):
        # Arrange
        data = {'items': '1'}

        # Act
        response = self.client.delete(self.url, data)

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'

    def test_put_contact_authenticated(self):
        # Arrange
        user = baker.make(User)
        contact = baker.make(Contact, user=user, city='Old City')
        self.client.force_authenticate(user=user)
        data = {'id': contact.id, 'city': 'New City'}


        # Act
        response = self.client.put(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True
        contact.refresh_from_db()
        assert contact.city == 'New City'

    def test_put_contact_unauthenticated(self):
        # Arrange
        data = {'id': '1', 'city': 'New City'}

        # Act
        response = self.client.put(self.url, data)

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'


@pytest.mark.django_db
class TestOrderView:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('backend:order') 

    def authenticate_user(self, user_type, email='shopuser@example.com', password='password123'):
        # Создаем пользователя
        user = baker.make('backend.User', email=email, type=user_type, is_active=True)
        user.set_password(password)
        user.save()

        # Выполняем запрос для получения токена
        login_url = reverse('backend:user-login')
        response = self.client.post(login_url, {'email': email, 'password': password})

        # Убеждаемся, что получили токен
        assert response.status_code == 200
        token = response.json().get('Token')
        assert token is not None, "Token is None. Authentication failed."

        # Устанавливаем токен для последующих запросов
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        return user

    def test_get_orders_authenticated(self):
        # Arrange
        user = self.authenticate_user('shop')

        # Удаляем все заказы пользователя перед тестом
        Order.objects.filter(user=user).delete()
        
        # Создаем несколько заказов
        for _ in range(3):
            baker.make('backend.Order', user=user)

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 200
        assert len(response.data) == 3  # Проверяем, что возвращается 3 заказа

    def test_get_orders_unauthenticated(self):
        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'

    def test_post_order_authenticated(self):
        # Arrange
        user = baker.make(User)
        contact = baker.make(Contact, user=user)
        order = baker.make(Order, user=user, state='basket')
        self.client.force_authenticate(user=user)
        data = {'id': order.id, 'contact': contact.id}

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True
        order.refresh_from_db()
        assert order.state == 'new'

    def test_post_order_unauthenticated(self):
        # Arrange
        data = {'id': '1', 'contact': '1'}

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'

    def test_put_order_authenticated(self):
        # Arrange
        user = baker.make(User)
        order = baker.make(Order, user=user, state='new')
        contact = baker.make(Contact, user=user)
        self.client.force_authenticate(user=user)
        data = {'id': order.id, 'contact': contact.id, 'state': 'processing'}

        # Act
        response = self.client.put(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True
        order.refresh_from_db()
        assert order.contact_id == contact.id
        assert order.state == 'processing'

    def test_put_order_unauthenticated(self):
        # Arrange
        data = {'id': '1', 'contact': '1', 'state': 'processing'}

        # Act
        response = self.client.put(self.url, data)

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'

    def test_delete_order_authenticated(self):
        # Arrange
        user = baker.make(User)
        order = baker.make(Order, user=user, state='new')
        self.client.force_authenticate(user=user)
        data = {'id': order.id}

        # Act
        response = self.client.delete(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True
        assert not Order.objects.filter(id=order.id).exists()

    def test_delete_order_unauthenticated(self):
        # Arrange
        data = {'id': '1'}

        # Act
        response = self.client.delete(self.url, data)

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'

    def test_delete_active_basket_order(self):
        # Arrange
        user = baker.make(User)
        order = baker.make(Order, user=user, state='basket')
        self.client.force_authenticate(user=user)
        data = {'id': order.id}

        # Act
        response = self.client.delete(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Cannot delete an active basket order'
        assert Order.objects.filter(id=order.id).exists()


@pytest.mark.django_db
class TestBasketView:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('backend:basket')


    def authenticate_user(self, user_type, email='shopuser@example.com', password='password123'):
        user = baker.make('backend.User', email=email, type=user_type, is_active=True) 
        user.set_password(password)
        user.save()

        # Выполняем запрос для получения токена
        login_url = reverse('backend:user-login')
        response = self.client.post(login_url, {'email': email, 'password': password})

        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.content}")

        # Убеждаемся, что получили токен
        assert response.status_code == 200
        token = response.json().get('Token')
        assert token is not None, "Token is None. Authentication failed."

        # Устанавливаем токен для последующих запросов
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        return user

    def test_get_basket_unauthenticated(self):
        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'


    def test_post_basket_unauthenticated(self):
        # Arrange
        data = {'items': [{'product_info': '1', 'quantity': 2}]}

        # Act
        response = self.client.post(self.url, data, content_type='application/json')

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'


    def test_delete_basket_unauthenticated(self):
        # Arrange
        data = {'items': '1'}

        # Act
        response = self.client.delete(self.url, data, content_type='application/json')

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'


    def test_put_basket_unauthenticated(self):
        # Arrange
        data = {'items': json.dumps([{'id': '1', 'quantity': 5}])}

        # Act
        response = self.client.put(self.url, data, content_type='application/json')

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'
    

@pytest.mark.django_db
class TestProductInfoView:
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        # Создаем необходимые объекты
        self.shop = baker.make(Shop, state=True)
        self.category = baker.make(Category)
        self.product = baker.make(Product, category=self.category)
        self.product_info = baker.make(ProductInfo, shop=self.shop, product=self.product)
        
    def test_get_product_info_success(self):
        # Arrange: Убедимся, что в базе есть данные
        url = reverse('backend:shops') 
        expected_data = ProductInfoSerializer([self.product_info], many=True).data
        
        # Act: Выполняем запрос
        response = self.client.get(url, {'shop_id': self.shop.id, 'category_id': self.category.id})
        
        # Assert: Проверяем результаты
        assert response.status_code == status.HTTP_200_OK
        assert response.data == expected_data

    def test_get_product_info_not_found(self):
        # Arrange: Убедимся, что в базе нет данных
        url = reverse('backend:shops') 
        expected_data = []
        
        # Act: Выполняем запрос
        response = self.client.get(url, {'shop_id': 999, 'category_id': 999})
        
        # Assert: Проверяем результаты
        assert response.status_code == status.HTTP_200_OK
        assert response.data == expected_data

@pytest.mark.django_db
class TestPartnerState:
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.url = reverse('backend:partner-state')
    
    def authenticate_user(self, user_type, email='shopuser@example.com', password='password123'):
        # Создаем пользователя
        user = baker.make('backend.User', email=email, type=user_type, is_active=True)
        user.set_password(password)
        user.save()

        # Выполняем запрос для получения токена
        login_url = reverse('backend:user-login')
        response = self.client.post(login_url, {'email': email, 'password': password})

        # Убеждаемся, что получили токен
        assert response.status_code == 200
        token = response.json().get('Token')
        assert token is not None, "Token is None. Authentication failed."

        # Устанавливаем токен для последующих запросов
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        return user

    def test_get_partner_state_not_shop_user(self):
        # Arrange
        user = self.authenticate_user('buyer')

        # Act 
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data == {'Status': False, 'Error': 'Только для магазинов'}


    def test_post_partner_state_not_authenticated(self):
        # Act  
        response = self.client.post(self.url, {'state': True}, format='json')

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data == {'Status': False, 'Error': 'Log in required'}

    def test_post_partner_state_not_shop_user(self):
        # Arrange
        user = self.authenticate_user('buyer')

        # Act
        response = self.client.post(self.url, {'state': True}, format='json')

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data == {'Status': False, 'Error': 'Только для магазинов'}



@pytest.mark.django_db
class TestPartnerUpdate:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('backend:partner-update')

    def test_unauthenticated_user(self):
        response = self.client.post(self.url)
        assert response.status_code == 403
        assert response.data['Error'] == 'Log in required'

    def test_non_shop_user(self):
        user = baker.make(User, type='buyer')
        self.client.force_authenticate(user=user)

        response = self.client.post(self.url)
        assert response.status_code == 403
        assert response.data['Error'] == 'Только для магазинов'

    def test_missing_url(self):
        user = baker.make(User, type='shop')
        self.client.force_authenticate(user=user)

        response = self.client.post(self.url, {})
        assert response.status_code == 400
        assert response.data['Errors'] == 'Не указаны все необходимые аргументы'

    def test_invalid_url(self):
        user = baker.make(User, type='shop')
        self.client.force_authenticate(user=user)

        invalid_url = 'invalid-url'
        response = self.client.post(self.url, {'url': invalid_url})

        assert response.status_code == 400
        assert 'Error' in response.data



@pytest.mark.django_db
class TestPartnerOrdersView:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('backend:partner-orders')  


    def authenticate_user(self, user_type, email='shopuser@example.com', password='password123'):
        user = baker.make('backend.User', email=email, type=user_type, is_active=True) 
        user.set_password(password)
        user.save()

        # Выполняем запрос для получения токена
        login_url = reverse('backend:user-login')
        response = self.client.post(login_url, {'email': email, 'password': password})

        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.content}")

        # Убеждаемся, что получили токен
        assert response.status_code == 200
        token = response.json().get('Token')
        assert token is not None, "Token is None. Authentication failed."

        # Устанавливаем токен для последующих запросов
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        return user

    def test_get_partner_orders_authenticated_shop_user(self):
        # Arrange: Аутентифицируем пользователя и сохраняем его
        user = self.authenticate_user('shop')

        shop = baker.make('Shop', user=user)
        category = baker.make('Category')
        product = baker.make('Product', category=category)
        product_info = baker.make('ProductInfo', product=product, shop=shop, price=1000, quantity=10)
        order = baker.make('Order', user=user, state='new')

        # Создаем OrderItem
        baker.make('OrderItem', order=order, product_info=product_info, quantity=2)

        # Act: Выполняем GET запрос к защищенному эндпоинту
        response = self.client.get(self.url)

        # Assert: Проверяем корректность ответа
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['id'] == order.id

    def test_get_partner_orders_not_authenticated(self):
        # Act
        response = self.client.get(self.url)

        # Получение данных из ответа
        response_data = response.json()

        # Assert
        assert response.status_code == 403
        assert response_data['Error'] == 'Log in required'

    def test_get_partner_orders_non_shop_user(self):
        # Arrange
        user = self.authenticate_user('buyer')
        # Act
        response = self.client.get(self.url)

        # Получение данных из ответа
        response_data = response.json()

        # Assert
        assert response.status_code == 403
        assert response_data['Error'] == 'Только для магазинов'

    def test_get_partner_orders_no_orders(self):
        # Arrange
        user = self.authenticate_user('shop')

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 200
        assert response.data == []

    def test_get_partner_orders_excludes_basket(self):
        # Arrange
        user = self.authenticate_user('shop')

        shop = baker.make('Shop', user=user)
        category = baker.make('Category')  # Создайте категорию
        product = baker.make('Product', category=category)  # Укажите категорию при создании продукта
        product_info = baker.make('ProductInfo', shop=shop, product=product)  # Указываем product и shop
        basket_order = baker.make('Order', state='basket', user=user)  # Укажите пользователя при создании заказа
        baker.make('OrderItem', order=basket_order, product_info=product_info)

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 200
        assert response.data == []