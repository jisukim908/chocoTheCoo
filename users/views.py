import django.db.utils
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import (CustomTokenObtainPairSerializer, UserSerializer, DeliverieSerializer, ReadUserSerializer, SellerSerializer)
from .models import User,Deliverie,Seller
from django.contrib.auth.hashers import check_password
from . import validated
from . cryption import AESAlgorithm

class GetEmailAuthCodeAPIView(APIView):
    """ 이메일 인증코드 발송 """
    def put(self, request):
        """ 이메일 인증코드 발송 및 DB 저장 """
        user = get_object_or_404(User, email=request.data['email'])
        auth_code = validated.send_email(user.email)
        user.auth_code = auth_code
        print(auth_code)
        user.save()
        return Response({"msg": "인증 코드를 발송 했습니다."}, status=status.HTTP_400_BAD_REQUEST)

class UserAPIView(APIView):
    """ 회원가입, 이메일 인증, 휴면 계정 전환"""
    def post(self,request):
        """ 회원 가입 """
        serializer = UserSerializer(data=request.data,context="create")
        if serializer.is_valid():
            serializer.save()
            return Response({'msg': "회원 가입 되었습니다. 계정 인증을 진행해 주세요."}, status=status.HTTP_200_OK)
        else:
            return Response({"err":serializer.errors},status=status.HTTP_400_BAD_REQUEST)

    def put(self,request):
        """ 회원 가입시 이메일 인증  or 휴면 계정 활성화 신청 응답 """
        user = get_object_or_404(User, email=request.data['email'])
        if user.auth_code == None:
            return Response({"mrr":"먼저 인증코드를 발급받아주세요."},status=status.HTTP_400_BAD_REQUEST)
        elif not user.auth_code == request.data['auth_code']:
            return Response({"err":"인증 코드가 올바르지 않습니다."},status=status.HTTP_400_BAD_REQUEST)
        else:
            user.is_active = True
            user.auth_code = None
            user.save()
            return Response({"msg": "인증 되었습니다."}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self,request):
        """ 비밀번호 재 설정(찾기 기능) """
        user = get_object_or_404(User,email = request.data['email'])
        if user.auth_code == '':
            return Response({"msg":"먼저 인증코드를 발급받아주세요."},status=status.HTTP_400_BAD_REQUEST)
        elif not user.auth_code == request.data['auth_code']:
            return Response({"err":"인증 코드가 올바르지 않습니다."},status=status.HTTP_401_UNAUTHORIZED)
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            user.auth_code = None
            user.is_active = True
            user.save()
            return Response({"msg":"비밀번호를 재 설정 했습니다."}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserProfileAPIView(APIView):
    """ 마이페이지 정보 읽기, 회원 정보 수정, 휴면 계정으로 전환 """
    def get(self, request,user_id):
        """ 마이페이지 정보 읽어오기 """
        user = get_object_or_404(User, id=user_id)
        serializer = ReadUserSerializer(user)
        result = serializer.decrypt(serializer.data)
        return Response(result, status=status.HTTP_200_OK)

    def put(self,request,user_id):
        """ 회원 정보 수정 (프로필 이미지, 닉네임, 통관번호, 이메일, 비밀번호) """
        user = get_object_or_404(User, id=user_id)
        if request.user != user:
            return Response({"err": "권한이 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = UserSerializer(user, data=request.data, partial=True,context="update")
        if serializer.is_valid():
            serializer.save()
            return Response({"msg": "회원 정보를 수정 했습니다."}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self,request,user_id):
        """ 휴면 계정으로 전환 """
        user = get_object_or_404(User, id=user_id)
        print(user, request.user)
        if request.user != user:
            return Response({"err": "권한이 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
        user.is_active = False
        user.save()
        return Response({"msg":"휴면 계정으로 전환 되었습니다."}, status=status.HTTP_200_OK)

class DeliverieAPIView(APIView):
    def get(self,request,user_id):
        """ 배송 정보들 읽기 """
        user = get_object_or_404(User, id=user_id)
        serializer = DeliverieSerializer(user.deliveries_data,many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request,user_id):
        """ 배송 정보 추가 """
        user = get_object_or_404(User, id=user_id)
        if request.user != user:
            return Response({'err': '권한이 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)
        deliverie_cnt = Deliverie.objects.filter(user=user).count()
        if deliverie_cnt > 4:
            return Response({'err': '배송 정보는 다섯개 까지 등록할 수 있습니다.'}, status=status.HTTP_400_BAD_REQUEST)
        if request.data.get("postal_code") != None:
            serializer = DeliverieSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(user=user)
                # deliverie = get_object_or_404(Deliverie, id=serializer.data.get('id'))
                # deliverie.delete()
                return Response({'msg': '배송 정보가 등록되었습니다.'}, status=status.HTTP_200_OK)
            else:
                return Response({"err": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        # 회원가입시 필수 입력 사항이 아니기 때문에 status code 를 204 사용
        return Response({'msg': '우편 번호 정보가 없습니다.'}, status=status.HTTP_204_NO_CONTENT)

class UpdateDeliverieAPIView(APIView):
    """ 배송 정보 수정 및 삭제 """
    def put(self,request,deliverie_id):
        """ 배송 정보 수정 """
        deliverie = get_object_or_404(Deliverie, id=deliverie_id)
        if request.user == deliverie.user:
            serializer = DeliverieSerializer(deliverie, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"err":"권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)

    def delete(self, request, deliverie_id):
        """ 배송 정보가 삭제 되었습니다."""
        deliverie = get_object_or_404(Deliverie, id=deliverie_id)
        if request.user == deliverie.user:
            deliverie.delete()
            return Response({"msg": "배송 정보가 삭제 되었습니다."}, status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({"err": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)

class SellerAPIView(APIView):
    def post(self,request):
        """ 판매자 정보 저장 및 권한 신청 """
        try:
            user = get_object_or_404(User,email=request.user.email)
        except AttributeError:
            return Response({'err': "로그인이 필요 합니다."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            serializer = SellerSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(user=user)
                return Response({'msg': "판매자 권한을 성공적으로 신청했습니다. 검증 후에 승인 됩니다."}, status=status.HTTP_200_OK)
            else:
                return Response({"err": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except django.db.utils.IntegrityError:
            return Response({"err": "이미 판매자 정보가 있습니다."}, status=status.HTTP_400_BAD_REQUEST)

    def put(self,request):
        """ 판매자 정보 수정 """
        try:
            user = get_object_or_404(User,email=request.user.email)
        except AttributeError:
            return Response({'err': "로그인이 필요 합니다."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = SellerSerializer(user.user_seller,data=request.data,partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'msg': "판매자 정보를 수정 했습니다."}, status=status.HTTP_200_OK)
        else:
            return Response({"err": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self,request):
        """ 판매자 정보 삭제 """
        try:
            user = get_object_or_404(User,email=request.user.email)
        except AttributeError:
            return Response({'err': "로그인이 필요 합니다."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user.user_seller.delete()
        except Seller.DoesNotExist:
            return Response({'err': "판매자 정보가 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'msg': "판매자 정보를 삭제 했습니다."}, status=status.HTTP_204_NO_CONTENT)

class SellerPermissionAPIView(APIView):
    """ 관리자가 판매자 정보 권한 승인 및 삭제 """
    def patch(self,request,user_id):
        """ 판매자 권한 승인 """
        try:
            admin = get_object_or_404(User, email=request.user.email)
        except AttributeError:
            return Response({'err': "로그인이 필요 합니다."}, status=status.HTTP_400_BAD_REQUEST)
        if not admin.is_admin:
            return Response({'err': "올바른 접근 방법이 아닙니다."}, status=status.HTTP_401_UNAUTHORIZED)
        user = get_object_or_404(User, id=user_id)
        user.is_seller = True
        user.save()
        return Response({'msg': "판매자 권한을 승인했습니다."}, status=status.HTTP_204_NO_CONTENT)

    def delete(self,request,user_id):
        """ 판매자 정보 삭제 """
        try:
            admin = get_object_or_404(User, email=request.user.email)
        except AttributeError:
            return Response({'err': "로그인이 필요 합니다."}, status=status.HTTP_400_BAD_REQUEST)
        if not admin.is_admin:
            return Response({'err': "올바른 접근 방법이 아닙니다."}, status=status.HTTP_401_UNAUTHORIZED)
        user = get_object_or_404(User, id=user_id)
        try:
            user.user_seller.delete()
        except Seller.DoesNotExist:
            return Response({'err': "판매자 정보가 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'msg': "판매자 정보를 삭제 했습니다."}, status=status.HTTP_204_NO_CONTENT)

class CustomTokenObtainPairView(TokenObtainPairView):
    """ 로그인 , access token 발급 """
    serializer_class = CustomTokenObtainPairSerializer

