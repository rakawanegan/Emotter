from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.views import View
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.files.base import ContentFile
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from PIL import Image
from io import BytesIO

from .models import Post, Connection, Comment
import base64
from fer import FER
import cv2
import numpy as np


class Home(LoginRequiredMixin, ListView):
    """HOMEページで、自分以外のユーザー投稿をリスト表示"""
    model = Post
    template_name = 'list.html'

    # def get_queryset(self):
    #     """リクエストユーザーのみ除外"""
    #     return Post.objects.exclude(user=self.request.user)
    
    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        #get_or_createにしないとサインアップ時オブジェクトがないためエラーになる
        context['connection'] = Connection.objects.get_or_create(user=self.request.user)
        return context
    

class MyPost(LoginRequiredMixin, ListView):
    """自分の投稿のみ表示"""
    model = Post
    template_name = 'list.html'

    def get_queryset(self):
        return Post.objects.filter(user=self.request.user)


class CreatePost(LoginRequiredMixin, CreateView):
    """投稿フォーム"""
    model = Post
    template_name = 'create.html'
    fields = ['content']
    success_url = reverse_lazy('mypost')

    def form_valid(self, form):
        """投稿ユーザーをリクエストユーザーと紐付け"""
        form.instance.user = self.request.user
        return super().form_valid(form)

@csrf_exempt
def face_emotion_predict(request):
    if request.method == 'POST':
        # bodyから画像データを取得
        image = request.body
        print(image)
        # imageのタイプを確認
        print(type(image))
        # # データは 'data:image/jpeg;base64,' で始まるため、それを取り除きます
        base64_data = str(image).split(',')[1]

        # strのデータをバイトデータに変換します
        byte_data = base64.b64decode(base64_data)

        # バイトデータをBytesIOオブジェクトに変換します
        image_data = BytesIO(byte_data)

        # BytesIOオブジェクトをPIL Imageオブジェクトに変換します
        img = Image.open(image_data)

        # PIL Imageオブジェクトをnumpy配列に変換します
        img_array = np.array(img)
        
        def txt2emo(txt):# テキストから感情を推定
            emotion_detector = None
            return 0

        def img2emo(img):# 画像から感情を推定
            emotion_detector = FER()
            return emotion_detector.top_emotion(img) # emotions = [angry, disgust, fear, happy, sad, surprise, neutral] example:(happy, 0.98)

        face_emotion, face_emotion_score = img2emo(img_array)
        # 画像から推定した感情を取得し、Postモデルのface_emotionに保存
        face_emotion_label = face_emotion
        text_emotion_label = txt2emo(request.POST['content'])

        post = Post()
        user = User.objects.get(id=request.POST['user_id'])
        post.content = request.POST['content']

        post.face_emotion = face_emotion_label
        post.text_emotion = text_emotion_label
        post.user = user
        post.save()

        return redirect('mypost')



class DetailPost(LoginRequiredMixin, DetailView):
    """投稿詳細ページ"""
    model = Post #Postモデルを指定
    template_name = 'detail.html' #テンプレートを指定

    def get_context_data(self, *args, **kwargs): #コメント機能
        context = super().get_context_data(*args, **kwargs) #親クラスのメソッドを呼び出す
        context['connection'] = Connection.objects.get_or_create(user=self.request.user) #フォロー機能
        context['comments'] = Comment.objects.filter(post=self.object) #コメントを取得
        return context

class CommentCreate(LoginRequiredMixin, CreateView): #コメント機能
    model = Comment
    template_name = 'create.html'
    fields = ['content']

    def get_context_data(self, **kwargs): 
        context = super().get_context_data(**kwargs)
        context['content'] = self.get_form()  # Add form to context
        return context

    def form_valid(self, form): 
        form.instance.user = self.request.user
        form.instance.post = Post.objects.get(pk=self.kwargs['pk'])
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('detail', kwargs={'pk': self.object.post.pk})

class UpdatePost(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """投稿編集ページ"""
    model = Post
    template_name = 'update.html'
    fields = ['content']


    def get_success_url(self,  **kwargs):
        """編集完了後の遷移先"""
        pk = self.kwargs["pk"]
        return reverse_lazy('detail', kwargs={"pk": pk})
    
    def test_func(self, **kwargs):
        """アクセスできるユーザーを制限"""
        pk = self.kwargs["pk"]
        post = Post.objects.get(pk=pk)
        return (post.user == self.request.user) 


class DeletePost(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """投稿編集ページ"""
    model = Post
    template_name = 'delete.html'
    success_url = reverse_lazy('mypost')

    def test_func(self, **kwargs):
        """アクセスできるユーザーを制限"""
        pk = self.kwargs["pk"]
        post = Post.objects.get(pk=pk)
        return (post.user == self.request.user) 


###############################################################
#いいね処理
class LikeBase(LoginRequiredMixin, View):
    """いいねのベース。リダイレクト先を以降で継承先で設定"""
    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        related_post = Post.objects.get(pk=pk)

        if self.request.user in related_post.like.all():
            obj = related_post.like.remove(self.request.user)
        else:
            obj = related_post.like.add(self.request.user)  
        return obj


class LikeHome(LikeBase):
    """HOMEページでいいねした場合"""
    def get(self, request, *args, **kwargs):
        super().get(request, *args, **kwargs)
        return redirect('home')


class LikeDetail(LikeBase):
    """詳細ページでいいねした場合"""
    def get(self, request, *args, **kwargs):
        super().get(request, *args, **kwargs)
        pk = self.kwargs['pk'] 
        return redirect('detail', pk)
###############################################################


###############################################################
#フォロー処理
class FollowBase(LoginRequiredMixin, View):
    """フォローのベース。リダイレクト先を以降で継承先で設定"""
    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        target_user = Post.objects.get(pk=pk).user

        my_connection = Connection.objects.get_or_create(user=self.request.user)

        if target_user in my_connection[0].following.all():
            obj = my_connection[0].following.remove(target_user)
        else:
            obj = my_connection[0].following.add(target_user)
        return obj

class FollowHome(FollowBase):
    """HOMEページでフォローした場合"""
    def get(self, request, *args, **kwargs):
        super().get(request, *args, **kwargs)
        return redirect('home')

class FollowDetail(FollowBase):
    """詳細ページでフォローした場合"""
    def get(self, request, *args, **kwargs):
        super().get(request, *args, **kwargs)
        pk = self.kwargs['pk'] 
        return redirect('detail', pk)
###############################################################


class FollowList(LoginRequiredMixin, ListView):
    """フォローしたユーザーの投稿をリスト表示"""
    model = Post
    template_name = 'list.html'

    def get_queryset(self):
        """フォローリスト内にユーザーが含まれている場合のみクエリセット返す"""
        my_connection = Connection.objects.get_or_create(user=self.request.user)
        all_follow = my_connection[0].following.all()
        return Post.objects.filter(user__in=all_follow)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['connection'] = Connection.objects.get_or_create(user=self.request.user)
        return context

