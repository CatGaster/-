import pytest
import json
import yaml

from django.urls import reverse
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
from django.db.models import Q, Sum, F
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from model_bakery import baker
from backend.models import User, ConfirmEmailToken, Category, Shop, Contact, Order, Product, ProductInfo, OrderItem, Parameter, ProductParameter
from unittest.mock import patch

from backend.serializers import ProductInfoSerializer



@pytest.mark.django_db
class TestRegisterAccount:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('user/register')

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


@pytest.mark.django_db
class TestConfirmAccount:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('user/register/confirm')

    def test_confirm_account_success(self):
        # Arrange
        user = baker.make(User, email='john.doe@example.com', is_active=False)
        token = baker.make(ConfirmEmailToken, user=user)

        data = {
            'email': user.email,
            'token': token.key
        }

        # Act   
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True

        user.refresh_from_db()
        assert user.is_active is True
        assert not ConfirmEmailToken.objects.filter(user=user).exists()

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


@pytest.mark.django_db
class TestAccountDetails:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('user/details')
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


@pytest.mark.django_db
class TestLoginAccount:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('user/login')

    def test_login_success(self):
        # Arrange
        user = baker.make(User, email='john.doe@example.com')
        user.set_password('password123')
        user.save()

        data = {
            'email': 'john.doe@example.com',
            'password': 'password123'
        }

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True
        assert 'Token' in response.json()

        token = Token.objects.get(user=user)
        assert response.json()['Token'] == token.key
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == 'Ваш токен для доступа на нашем сайте'
        assert token.key in mail.outbox[0].body

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


@pytest.mark.django_db
class TestCategoryView:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('categories') 

    def test_get_categories(self):
        # Arrange
        categories = baker.make(Category, _quantity=3)

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 200
        assert len(response.json()) == 3
        returned_names = [category['name'] for category in response.json()]
        expected_names = [category.name for category in categories]
        assert set(returned_names) == set(expected_names)

    def test_get_empty_categories(self):
        # Arrange
        # Нет категорий в базе данных

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 200
        assert len(response.json()) == 0


@pytest.mark.django_db
class TestShopView:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('shops')  

    def test_get_active_shops(self):
        # Arrange
        active_shops = baker.make(Shop, state=True, _quantity=3)
        inactive_shops = baker.make(Shop, state=False, _quantity=2)

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 200
        assert len(response.json()) == 3
        returned_names = [shop['name'] for shop in response.json()]
        expected_names = [shop.name for shop in active_shops]
        assert set(returned_names) == set(expected_names)

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
        self.url = reverse('user/change/type')  

    def test_change_user_type_to_shop(self):
        # Arrange
        user = baker.make(User, type='buyer')
        user.set_password('password123')
        user.save()
        self.client.force_authenticate(user=user)

        data = {'password': 'password123'}

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True
        assert response.json()['Message'] == 'User type updated to shop'
        
        user.refresh_from_db()
        assert user.type == 'shop'

    def test_change_user_type_to_buyer(self):
        # Arrange
        user = baker.make(User, type='shop')
        user.set_password('password123')
        user.save()
        self.client.force_authenticate(user=user)

        data = {'password': 'password123'}

        # Act
        response = self.client.post(self.url, data)

        # Assert
        assert response.status_code == 200
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
        assert response.json()['Error'] == 'Invalid password'

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
        self.url = reverse('user/contact')

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
        self.url = reverse('order') 
    def test_get_orders_authenticated(self):
        # Arrange
        user = baker.make(User)
        self.client.force_authenticate(user=user)
        baker.make(Order, user=user, _quantity=3)

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 200
        assert len(response.data) == 3

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
        self.url = reverse('basket')

    def test_get_basket_authenticated(self):
        # Arrange
        user = baker.make(User)
        self.client.force_authenticate(user=user)
        basket = baker.make(Order, user=user, state='basket')
        baker.make(OrderItem, order=basket, _quantity=3)

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 200
        assert len(response.data) == 1  # Возвращается только корзина с указанными товарами
        assert len(response.data[0]['ordered_items']) == 3

    def test_get_basket_unauthenticated(self):
        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'

    def test_post_basket_authenticated(self):
        # Arrange
        user = baker.make(User)
        self.client.force_authenticate(user=user)
        product = baker.make(Product)
        basket = Order.objects.create(user=user, state='basket')
        data = {'items': [{'product_info': product.id, 'quantity': 2}]}

        # Act
        response = self.client.post(self.url, data, content_type='application/json')

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True
        assert OrderItem.objects.filter(order=basket).count() == 1

    def test_post_basket_authenticated_form_data(self):
        # Arrange
        user = baker.make(User)
        self.client.force_authenticate(user=user)
        product = baker.make(Product)
        basket = Order.objects.create(user=user, state='basket')
        data = {'items': json.dumps([{'product_info': product.id, 'quantity': 2}])}

        # Act
        response = self.client.post(self.url, data, content_type='application/x-www-form-urlencoded')

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True
        assert OrderItem.objects.filter(order=basket).count() == 1

    def test_post_basket_unauthenticated(self):
        # Arrange
        data = {'items': [{'product_info': '1', 'quantity': 2}]}

        # Act
        response = self.client.post(self.url, data, content_type='application/json')

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'

    def test_delete_basket_authenticated(self):
        # Arrange
        user = baker.make(User)
        self.client.force_authenticate(user=user)
        basket = Order.objects.create(user=user, state='basket')
        order_item = baker.make(OrderItem, order=basket)
        data = {'items': str(order_item.id)}

        # Act
        response = self.client.delete(self.url, data, content_type='application/json')

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True
        assert not OrderItem.objects.filter(id=order_item.id).exists()

    def test_delete_basket_unauthenticated(self):
        # Arrange
        data = {'items': '1'}

        # Act
        response = self.client.delete(self.url, data, content_type='application/json')

        # Assert
        assert response.status_code == 403
        assert response.json()['Status'] is False
        assert response.json()['Error'] == 'Log in required'

    def test_put_basket_authenticated(self):
        # Arrange
        user = baker.make(User)
        self.client.force_authenticate(user=user)
        basket = Order.objects.create(user=user, state='basket')
        order_item = baker.make(OrderItem, order=basket, quantity=1)
        data = {'items': json.dumps([{'id': order_item.id, 'quantity': 5}])}

        # Act
        response = self.client.put(self.url, data, content_type='application/json')

        # Assert
        assert response.status_code == 200
        assert response.json()['Status'] is True
        order_item.refresh_from_db()
        assert order_item.quantity == 5

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
        url = reverse('products') 
        expected_data = ProductInfoSerializer([self.product_info], many=True).data
        
        # Act: Выполняем запрос
        response = self.client.get(url, {'shop_id': self.shop.id, 'category_id': self.category.id})
        
        # Assert: Проверяем результаты
        assert response.status_code == status.HTTP_200_OK
        assert response.data == expected_data

    def test_get_product_info_no_filters(self):
        # Arrange: Убедимся, что в базе есть данные
        url = reverse('products') 
        expected_data = ProductInfoSerializer([self.product_info], many=True).data
        
        # Act: Выполняем запрос без фильтров
        response = self.client.get(url)
        
        # Assert: Проверяем результаты
        assert response.status_code == status.HTTP_200_OK
        assert response.data == expected_data

    def test_get_product_info_no_active_shops(self):
        # Arrange: Создаем неактивный магазин
        inactive_shop = baker.make(Shop, state=False)
        baker.make(ProductInfo, shop=inactive_shop, product=self.product)
        url = reverse('products')
        
        # Act: Выполняем запрос
        response = self.client.get(url)
        
        # Assert: Убедимся, что в ответе нет данных из неактивного магазина
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_get_product_info_invalid_shop_id(self):
        # Act: Выполняем запрос с неверным shop_id
        url = reverse('products')
        response = self.client.get(url, {'shop_id': 'invalid_id'})
        
        # Assert: Убедимся, что результат пустой, так как нет данных
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_get_product_info_invalid_category_id(self):
        # Act: Выполняем запрос с неверным category_id
        url = reverse('products')
        response = self.client.get(url, {'category_id': 'invalid_id'})
        
        # Assert: Убедимся, что результат пустой, так как нет данных
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []


class TestPartnerState:
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
    
    def test_get_partner_state_success(self):
        # Arrange: Создаем необходимые объекты
        self.user = baker.make(User, type='shop', is_authenticated=True)
        self.shop = baker.make(Shop, user=self.user)
        self.client.force_authenticate(user=self.user)

        # Act: Выполняем запрос
        url = reverse('partner/state') 
        response = self.client.get(url)

        # Assert: Проверяем результаты
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == self.shop.id
        assert response.data['name'] == self.shop.name
        assert response.data['url'] == self.shop.url
        assert response.data['state'] == self.shop.state

    def test_get_partner_state_not_authenticated(self):
        # Act
        url = reverse('partner/state')  
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data == {'Status': False, 'Error': 'Log in required'}

    def test_get_partner_state_not_shop_user(self):
        # Arrange
        self.user = baker.make(User, type='buyer', is_authenticated=True)
        self.client.force_authenticate(user=self.user)

        # Act
        url = reverse('partner/state')  
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data == {'Status': False, 'Error': 'Только для магазинов'}

    def test_post_partner_state_success(self):
        # Arrange: Создаем необходимые объекты
        self.user = baker.make(User, type='shop', is_authenticated=True)
        self.shop = baker.make(Shop, user=self.user)
        self.client.force_authenticate(user=self.user)

        # Act: Выполняем запрос на изменение статуса
        url = reverse('partner/state')  
        response = self.client.post(url, {'state': True}, format='json')

        # Assert: Проверяем результаты
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {'Status': True}
        assert Shop.objects.get(user=self.user).state == True

    def test_post_partner_state_invalid_state(self):
        # Arrange
        self.user = baker.make(User, type='shop', is_authenticated=True)
        self.client.force_authenticate(user=self.user)

        # Act
        url = reverse('partner/state') 
        response = self.client.post(url, {'state': 'invalid'}, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {'Status': False, 'Errors': 'Invalid state value'}

    def test_post_partner_state_not_authenticated(self):
        # Act
        url = reverse('partner/state')  
        response = self.client.post(url, {'state': True}, format='json')

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data == {'Status': False, 'Error': 'Log in required'}

    def test_post_partner_state_not_shop_user(self):
        # Arrange
        self.user = baker.make(User, type='buyer', is_authenticated=True)
        self.client.force_authenticate(user=self.user)

        # Act
        url = reverse('partner/state')
        response = self.client.post(url, {'state': True}, format='json')

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data == {'Status': False, 'Error': 'Только для магазинов'}



@pytest.mark.django_db
class TestPartnerUpdate:
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.user = baker.make('User', type='shop')  # Создаем пользователя типа 'shop'
        self.client.force_authenticate(user=self.user)
        self.shop = baker.make(Shop, user=self.user)
        self.url = reverse('partner/update') 
    
    @patch('requests.get')
    @patch('yaml.load')
    def test_post_partner_update_success(self, mock_load, mock_requests_get):
        # Arrange
        mock_requests_get.return_value.status_code = 200
        mock_requests_get.return_value.content = b"""
        shop: "Test Shop"
        categories:
          - id: 1
            name: "Category 1"
        goods:
          - id: "123"
            name: "Product 1"
            category: 1
            model: "Model 1"
            price: 100
            price_rrc: 120
            quantity: 10
            parameters:
              color: "red"
        """
        mock_load.return_value = {
            'shop': 'Test Shop',
            'categories': [{'id': 1, 'name': 'Category 1'}],
            'goods': [{
                'id': '123',
                'name': 'Product 1',
                'category': 1,
                'model': 'Model 1',
                'price': 100,
                'price_rrc': 120,
                'quantity': 10,
                'parameters': {'color': 'red'}
            }]
        }

        # Act
        response = self.client.post(self.url, {'url': 'http://example.com/data.yaml'})
        
        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data == {'Status': True}
        assert Shop.objects.filter(name='Test Shop').exists()
        assert Category.objects.filter(id=1, name='Category 1').exists()
        assert Product.objects.filter(name='Product 1').exists()
        assert ProductInfo.objects.filter(shop=self.shop, external_id='123').exists()
        assert Parameter.objects.filter(name='color').exists()
        assert ProductParameter.objects.filter(value='red').exists()

    def test_post_partner_update_unauthenticated(self):
        # Arrange
        self.client.force_authenticate(user=None)
        
        # Act
        response = self.client.post(self.url, {'url': 'http://example.com/data.yaml'})
        
        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data == {'Status': False, 'Error': 'Log in required'}

    def test_post_partner_update_invalid_user_type(self):
        # Arrange
        invalid_user = baker.make('User', type='regular')
        self.client.force_authenticate(user=invalid_user)
        
        # Act
        response = self.client.post(self.url, {'url': 'http://example.com/data.yaml'})
        
        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data == {'Status': False, 'Error': 'Только для магазинов'}

    def test_post_partner_update_missing_url(self):
        # Act
        response = self.client.post(self.url, {})
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}

    
class TestPartnerOrdersView:

    def setup_method(self):
        self.client = APIClient()
        self.url = reverse('partner/orders')  

    def test_get_partner_orders_authenticated_shop_user(self):
        # Arrange
        user = baker.make('User', type='shop')
        self.client.force_authenticate(user=user)

        shop = baker.make('Shop', user=user)
        category = baker.make('Category')
        product = baker.make('Product', category=category)
        product_info = baker.make('ProductInfo', product=product, shop=shop)
        order = baker.make('Order', user=user, state='new')
        baker.make('OrderItem', order=order, product_info=product_info, quantity=2, _quantity=3)

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['id'] == order.id

    def test_get_partner_orders_not_authenticated(self):
        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 403
        assert response.data['Error'] == 'Log in required'

    def test_get_partner_orders_non_shop_user(self):
        # Arrange
        user = baker.make('User', type='buyer')
        self.client.force_authenticate(user=user)

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 403
        assert response.data['Error'] == 'Только для магазинов'

    def test_get_partner_orders_no_orders(self):
        # Arrange
        user = baker.make('User', type='shop')
        self.client.force_authenticate(user=user)

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 200
        assert response.data == []

    def test_get_partner_orders_excludes_basket(self):
        # Arrange
        user = baker.make('User', type='shop')
        self.client.force_authenticate(user=user)

        shop = baker.make('Shop', user=user)
        product_info = baker.make('ProductInfo', shop=shop)
        basket_order = baker.make('Order', state='basket')
        baker.make('OrderItem', order=basket_order, product_info=product_info)

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == 200
        assert response.data == []