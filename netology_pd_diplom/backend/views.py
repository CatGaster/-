import json
import requests
from rest_framework.request import Request
from django.contrib.auth.hashers import check_password
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.core.mail import send_mail 
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from rest_framework import status
from django.conf import settings
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from ujson import loads as load_json
from yaml import load as load_yaml, Loader


from backend.strbool import strbool

from backend.models import User, Shop, Category, Product, ProductInfo, Parameter, ProductParameter, Order, OrderItem, \
    Contact, ConfirmEmailToken
from backend.serializers import UserSerializer, CategorySerializer, ShopSerializer, ProductInfoSerializer, \
    OrderItemSerializer, OrderSerializer, ContactSerializer
from backend.signals import new_user_registered, new_order

class RegisterAccount(APIView):
    """
    Класс для регистрации новых пользователей. 
    Позволяет создать учетную запись пользователя с проверкой сложности пароля и уникальности данных.

    Методы:
    -post
    """
    # Регистрация методом POST
    def post(self, request, *args, **kwargs):
        """
        Обрабатывает POST-запрос для создания нового пользователя. Проверяет наличие всех необходимых полей и сохраняет пользователя в базе данных.

            Args:
                request (Request): The Django request object.

            Returns:
                JsonResponse: The response indicating the status of the operation and any errors.
            """
        # проверяем обязательные аргументы
        if {'first_name', 'last_name', 'email', 'password', 'company', 'position'}.issubset(request.data):

            # проверяем пароль на сложность
            sad = 'asd'
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:
                # проверяем данные для уникальности имени пользователя

                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():
                    # сохраняем пользователя
                    user = user_serializer.save()
                    user.set_password(request.data['password'])
                    user.save()
                    return JsonResponse({'Status': True})
                else:
                    return JsonResponse({'Status': False, 'Errors': user_serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class ConfirmAccount(APIView):
    """
    Класс для подтверждения почтового адреса
    Методы:
    - post
    """
    # Регистрация методом POST
    def post(self, request, *args, **kwargs):
        """
                Подтверждает почтовый адрес пользователя.

                Args:
                - request (Request): The Django request object.

                Returns:
                - JsonResponse: The response indicating the status of the operation and any errors.
                """
        # проверяем обязательные аргументы
        if {'email', 'token'}.issubset(request.data):

            token = ConfirmEmailToken.objects.filter(user__email=request.data['email'],
                                                     key=request.data['token']).first()
            if token:
                token.user.is_active = True
                token.user.save()
                token.delete()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': 'Неправильно указан токен или email'})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class AccountDetails(APIView):
    """
    Класс для управления деталями аккаунта пользователя.
    Позволяет просматривать и обновлять данные аутентифицированного пользователя.

    Методы:
    - get
    - post

    Attributes:
    - None
    """

    # получить данные
    def get(self, request: Request, *args, **kwargs):
        """
              Обрабатывает GET-запрос для получения деталей аутентифицированного пользователя.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the details of the authenticated user.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    # Редактирование методом POST
    def post(self, request, *args, **kwargs):
        """
            Обрабатывает POST-запрос для обновления деталей аутентифицированного пользователя. 
            Поддерживает обновление пароля и других данных пользователя


                Args:
                - request (Request): The Django request object.

                Returns:
                - JsonResponse: The response indicating the status of the operation and any errors.
                """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        # проверяем обязательные аргументы

        if 'password' in request.data:
            errors = {}
            # проверяем пароль на сложность
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:
                request.user.set_password(request.data['password'])

        # проверяем остальные данные
        user_serializer = UserSerializer(request.user, data=request.data, partial=True)
        if user_serializer.is_valid():
            user_serializer.save()
            return JsonResponse({'Status': True})
        else:
            return JsonResponse({'Status': False, 'Errors': user_serializer.errors})


class LoginAccount(APIView):
    """
    Класс для авторизации пользователей
    """

    # Авторизация методом POST
    def post(self, request, *args, **kwargs):
        """
                Authenticate a user.

                Args:
                    request (Request): The Django request object.

                Returns:
                    JsonResponse: The response indicating the status of the operation and any errors.
                """
        if {'email', 'password'}.issubset(request.data):
            user = authenticate(request, username=request.data['email'], password=request.data['password'])

            if user is not None:
                if user.is_active:
                    token, _ = Token.objects.get_or_create(user=user)

                    # Отправка email с токеном пользователя
                    subject = 'Ваш токен для доступа на нашем сайте'
                    message = f'Здравствуйте, {user.username}!\n\nВаш токен: {token.key}\nИспользуйте его для доступа к нашим сервисам.'
                    email_from = settings.DEFAULT_FROM_EMAIL
                    recipient_list = [user.email]

                    send_mail(subject, message, email_from, recipient_list)

                    return JsonResponse({'Status': True, 'Token': token.key})

            return JsonResponse({'Status': False, 'Errors': 'Не удалось авторизовать'})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class CategoryView(ListAPIView):
    """
    Класс для просмотра категорий

    Методы:
    **get(request: Request, *args, kwargs):

    Атрибуты:
        queryset:
        Запрос к базе данных, который получает все записи из модели Category.

        serializer_class:
        Сериализатор, используемый для преобразования объектов категории в формат 
        JSON (CategorySerializer).
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):
    """
    Класс для просмотра списка магазинов

    Методы:
    **get(request: Request, *args, kwargs):

    Атрибуты:
        queryset:
        Запрос к базе данных, который получает все записи из модели Shop.

        serializer_class:
        Сериализатор, используемый для преобразования объектов магазина в формат 
        JSON (ShopSerializer).
    """

    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    """
        Класс для просмотра информации о продуктах.

        Методы:
        - get

        Attributes:
        - None
        """

    def get(self, request: Request, *args, **kwargs):
        """
               Возвращает информацию о продуктах на основе указанных фильтров (магазин и/или категория).
                Если фильтры не заданы, возвращаются все доступные продукты из активных магазинов.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the product information.
               """
        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')

        if shop_id:
            query = query & Q(shop_id=shop_id)

        if category_id:
            query = query & Q(product__category_id=category_id)

        # фильтруем и отбрасываем дубликаты
        queryset = ProductInfo.objects.filter(
            query).select_related(
            'shop', 'product__category').prefetch_related(
            'product_parameters__parameter').distinct()

        serializer = ProductInfoSerializer(queryset, many=True)

        return Response(serializer.data)


class BasketView(APIView):
    """
    Класс для управления корзиной пользователя. Позволяет просматривать, добавлять, обновлять и удалять товары в корзине.
    Аутентификация: Все операции с корзиной требуют аутентификации.

    Методы:
    - get
    - post
    - put
    - delete

    Attributes:
    - None
    """

    # получить корзину
    def get(self, request, *args, **kwargs):
        """
                Возвращает список товаров в корзине пользователя.

                Args:
                - request (Request): The Django request object.

                Returns:
                - Response: The response containing the items in the user's basket.
                """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        basket = Order.objects.filter(
            user_id=request.user.id, state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    # редактировать корзину
    def post(self, request, *args, **kwargs):
        """
        Добавляет товары в корзину пользователя.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        # Проверяем тип контента
        if request.content_type == 'application/json':
            # Если контент JSON, получаем данные напрямую
            items = request.data.get('items')
        else:
            # Если контент form-data, извлекаем строку и парсим в JSON
            items_str = request.POST.get('items')
            try:
                items = json.loads(items_str) if items_str else []
            except json.JSONDecodeError:
                return JsonResponse({'Status': False, 'Errors': 'Invalid JSON format in form-data'}, status=400)

        if items:
            basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
            objects_created = 0
            for order_item in items:
                order_item.update({'order': basket.id})
                serializer = OrderItemSerializer(data=order_item)
                if serializer.is_valid():
                    try:
                        serializer.save()
                    except IntegrityError as error:
                        return JsonResponse({'Status': False, 'Errors': str(error)})
                    else:
                        objects_created += 1
                else:
                    return JsonResponse({'Status': False, 'Errors': serializer.errors})
            return JsonResponse({'Status': True, 'Создано объектов': objects_created})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # удалить товары из корзины
    def delete(self, request, *args, **kwargs):
        """
                Удаляет товары из корзины пользователя.

                Args:
                - request (Request): The Django request object.

                Returns:
                - JsonResponse: The response indicating the status of the operation and any errors.
                """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
            query = Q()
            objects_deleted = False
            for order_item_id in items_list:
                if order_item_id.isdigit():
                    query = query | Q(order_id=basket.id, id=order_item_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = OrderItem.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # добавить позиции в корзину
    def put(self, request, *args, **kwargs):
        """
               Обновляет количество товаров в корзине пользователя.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            try:
                items_dict = load_json(items_sting)
            except ValueError:
                return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})
            else:
                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_updated = 0
                for order_item in items_dict:
                    if type(order_item['id']) == int and type(order_item['quantity']) == int:
                        objects_updated += OrderItem.objects.filter(order_id=basket.id, id=order_item['id']).update(
                            quantity=order_item['quantity'])

                return JsonResponse({'Status': True, 'Обновлено объектов': objects_updated})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class PartnerUpdate(APIView):
    """
    Класс для обновления информации о партнерах (магазинах) и их продуктах.
    Партнеры могут загружать данные о своем магазине и продуктах через YAML-файл.

    Аутентификация и авторизация: Пользователь должен быть аутентифицирован и иметь тип "shop".
    Если пользователь не аутентифицирован или его тип не "shop", операция будет отклонена.

    Методы:
    POST: 

    Валидация URL:
    Перед запросом URL проходит валидацию. Если URL некорректен, возвращается ошибка.
    
    """

    def post(self, request, *args, **kwargs):
        """
            Обрабатывает POST-запрос для обновления информации о магазине и его продуктах. Данные берутся из YAML-файла, URL которого передается в теле запроса.

            Возвращает:
            - JsonResponse: Статус операции и ошибки.
        """
            

        if not request.user.is_authenticated:
            return Response({'Status': False, 'Error': 'Log in required'}, status=status.HTTP_403_FORBIDDEN)

        if request.user.type != 'shop':
            return Response({'Status': False, 'Error': 'Только для магазинов'}, status=status.HTTP_403_FORBIDDEN)

        url = request.data.get('url')
        if not url:
            return Response({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=status.HTTP_400_BAD_REQUEST)
        
        validate_url = URLValidator()
        try:
            validate_url(url)
        except ValidationError as e:
            return Response({'Status': False, 'Error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            stream = response.content

            data = load_yaml(stream, Loader=Loader)

            shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=request.user.id)
            
            for category in data['categories']:
                category_object, _ = Category.objects.get_or_create(
                    id=category['id'],
                    defaults={'name': category['name']}
                )
                category_object.shops.add(shop)
                category_object.save()

            for item in data['goods']:
                product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])

                # Обновление или создание ProductInfo
                product_info, created = ProductInfo.objects.update_or_create(
                    shop=shop,
                    external_id=item['id'],
                    defaults={
                        'product': product,
                        'model': item['model'],
                        'price': item['price'],
                        'price_rrc': item['price_rrc'],
                        'quantity': item['quantity'],
                    }
                )

                # Обновляем параметры товара
                for name, value in item['parameters'].items():
                    parameter_object, _ = Parameter.objects.get_or_create(name=name)
                    ProductParameter.objects.update_or_create(
                        product_info=product_info,
                        parameter=parameter_object,
                        defaults={'value': value}
                    )

            return Response({'Status': True}, status=status.HTTP_201_CREATED)

        except requests.exceptions.RequestException as e:
            return Response({'Status': False, 'Error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PartnerState(APIView):
    """
       Класс для управления статусом партнера (магазина). 
       Позволяет просматривать текущий статус партнера и обновлять его.

       Методы:
       - get
       - post

       Attributes:
       - None
       """
    # получить текущий статус
    def get(self, request, *args, **kwargs):
        """
               Обрабатывает GET-запрос для получения текущего статуса партнера.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the state of the partner.
               """
        if not request.user.is_authenticated:
            return Response({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return Response({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    # изменить текущий статус
    def post(self, request, *args, **kwargs):
        """
               Обрабатывает POST-запрос для обновления текущего статуса партнера.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return Response({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return Response({'Status': False, 'Error': 'Только для магазинов'}, status=403)
        state = request.data.get('state')
        if state:
            try:
                Shop.objects.filter(user_id=request.user.id).update(state=strbool(state))
                return Response({'Status': True})
            except ValueError as error:
                return Response({'Status': False, 'Errors': str(error)})

        return Response({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class PartnerOrders(APIView):
    """
    Класс для получения заказов, связанных с аутентифицированным партнером (магазином)
    Методы:
    - get

    Attributes:
    - None
    """

    def get(self, request, *args, **kwargs):
        """
            Обрабатывает GET-запрос для получения списка заказов, связанных с аутентифицированным партнером (магазином).

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the orders associated with the partner.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        order = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)


class ContactView(APIView):
    """
      Класс для управления контактной информацией пользователя.
        Позволяет просматривать, добавлять, обновлять и удалять контакты аутентифицированного пользователя.

       Методы:
       - get
       - post
       - put
       - delete

       Attributes:
       - None
       """

    # получить мои контакты
    def get(self, request, *args, **kwargs):
        """
               Обрабатывает GET-запрос для получения контактной информации аутентифицированного пользователя.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the contact information.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        contact = Contact.objects.filter(
            user_id=request.user.id)
        serializer = ContactSerializer(contact, many=True)
        return Response(serializer.data)

    # добавить новый контакт
    def post(self, request, *args, **kwargs):
        """
               Обрабатывает POST-запрос для создания нового контакта для аутентифицированного пользователя.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if {'city', 'street', 'phone'}.issubset(request.data):
            request.data._mutable = True
            request.data.update({'user': request.user.id})
            serializer = ContactSerializer(data=request.data)

            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # удалить контакт
    def delete(self, request, *args, **kwargs):
        """
                Обрабатывает DELETE-запрос для удаления контактов аутентифицированного пользователя.

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            query = Q()
            objects_deleted = False
            for contact_id in items_list:
                if contact_id.isdigit():
                    query = query | Q(user_id=request.user.id, id=contact_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = Contact.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # редактировать контакт
    def put(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            """
                   Обрабатывает PUT-запрос для обновления контактной информации аутентифицированного пользователя.

                   Args:
                   - request (Request): The Django request object.

                   Returns:
                   - JsonResponse: The response indicating the status of the operation and any errors.
                   """
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if 'id' in request.data:
            if request.data['id'].isdigit():
                contact = Contact.objects.filter(id=request.data['id'], user_id=request.user.id).first()
                print(contact)
                if contact:
                    serializer = ContactSerializer(contact, data=request.data, partial=True)
                    if serializer.is_valid():
                        serializer.save()
                        return JsonResponse({'Status': True})
                    else:
                        return JsonResponse({'Status': False, 'Errors': serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class OrderView(APIView): 
    """
    Класс для управления заказами аутентифицированного пользователя.
    Позволяет просматривать список заказов, создавать новый заказ, обновлять существующий и удалять заказ.

    Методы:
    - get
    - post
    - put.
    - delete

    Attributes:
    - None
    """

    # получить мои заказы
    def get(self, request, *args, **kwargs):
        """
               Обрабатывает GET-запрос для получения списка заказов аутентифицированного пользователя.

               Args:
               - request (Request): The Django request object.

               Returns:
               - Response: The response containing the details of the order.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        order = Order.objects.filter(
            user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)
    
    # разместить заказ из корзины
    def post(self, request, *args, **kwargs):
        """
               Обрабатывает POST-запрос для размещения нового заказа из корзины

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if {'id', 'contact'}.issubset(request.data):
            if request.data['id'].isdigit():
                try:
                    is_updated = Order.objects.filter(
                        user_id=request.user.id, id=request.data['id']).update(
                        contact_id=request.data['contact'],
                        state='new')
                except IntegrityError as error:
                    print(error)
                    return JsonResponse({'Status': False, 'Errors': 'Неправильно указаны аргументы'})
                else:
                    if is_updated:
                        new_order.send(sender=self.__class__, user_id=request.user.id)
                        return JsonResponse({'Status': True})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})
    

    # обновить детали заказа
    def put(self, request, *args, **kwargs):
        """
        Обрабатывает PUT-запрос для обновления существующего заказа.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        order_id = request.data.get('id')
        if order_id and order_id.isdigit():
            try:
                order = Order.objects.get(id=order_id, user_id=request.user.id)
                
                # Проверка на изменения, которые пользователь хочет внести
                contact = request.data.get('contact')
                state = request.data.get('state')
                
                if contact:
                    order.contact_id = contact
                
                if state:
                    if state in ['new', 'processing', 'shipped', 'delivered']:
                        order.state = state
                    else:
                        return JsonResponse({'Status': False, 'Error': 'Invalid order state'}, status=400)
                
                order.save()
                return JsonResponse({'Status': True, 'Message': 'Order updated successfully'})
                
            except Order.DoesNotExist:
                return JsonResponse({'Status': False, 'Error': 'Order not found'}, status=404)
        return JsonResponse({'Status': False, 'Error': 'Invalid order ID'}, status=400)
    
    # удалить заказ
    def delete(self, request, *args, **kwargs):
        """
               Обрабатывает DELETE-запрос для удаления указанного заказа пользователя

               Args:
               - request (Request): The Django request object.

               Returns:
               - JsonResponse: The response indicating the status of the operation and any errors.
               """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        order_id = request.data.get('id')
        if order_id and order_id.isdigit():
            try:
                order = Order.objects.get(id=order_id, user_id=request.user.id)
                if order.state != 'basket':
                    order.delete()
                    return JsonResponse({'Status': True, 'Message': 'Order deleted'})
                else:
                    return JsonResponse({'Status': False, 'Error': 'Cannot delete an active basket order'})
            except Order.DoesNotExist:
                return JsonResponse({'Status': False, 'Error': 'Order not found'})
        return JsonResponse({'Status': False, 'Error': 'Invalid order ID'})


class ChangeUserType(APIView):
    """Проверяет, аутентифицирован ли пользователь и соответствует ли введённый пароль текущему паролю пользователя.
       Если проверка успешна, переключает тип пользователя на "shop" или "buyer"."""

    def post(self, request):
        """Обрабатывает POST-запрос для переключения типа пользователя."""
        
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        # Получаем пароль из запроса
        password = request.data.get('password')
        
        if not password:
            return JsonResponse({'Status': False, 'Error': 'Password is required'}, status=400)

        user = request.user

        # Проверяем, соответствует ли введённый пароль текущему паролю пользователя
        if not check_password(password, user.password):
            return JsonResponse({'Status': False, 'Error': 'Incorrect password'}, status=400)

        # Переключаем тип пользователя
        if user.type == 'buyer':
            user.type = 'shop'
            user.save()
            return JsonResponse({'Status': True, 'Message': 'User type updated to shop'})
        else:
            user.type = 'buyer'
            user.save()
            return JsonResponse({'Status': True, 'Message': 'User type updated to buyer'})