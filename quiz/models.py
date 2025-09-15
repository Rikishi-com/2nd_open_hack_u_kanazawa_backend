from django.db import models
from django.contrib.auth.models import User

# (変更なし) 分野モデル
class Field(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'name')

    def __str__(self):
        return self.name

# ✨【新規】答えモデル (answersテーブルに対応)
# これが「光合成」や「徳川家康」といった核になるデータです。
class Answer(models.Model):
    field = models.ForeignKey(Field, related_name='answers', on_delete=models.CASCADE)
    answer_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.answer_text

# ✨【新規】問題モデル (questionsテーブルに対応)
# 1つのAnswerに対して、このQuestionが複数ぶら下がります。
class Question(models.Model):
    answer = models.ForeignKey(Answer, related_name='questions', on_delete=models.CASCADE)
    question_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.question_text

# 🎯【変更】解答履歴モデル (attemptsテーブルに対応)
# どの「問題(Question)」に答えたかを記録します。
class Attempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE) # 紐づき先をItemからQuestionに変更
    is_correct = models.BooleanField()
    attempted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} - {self.question.question_text[:20]}'