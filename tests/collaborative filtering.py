# -*- coding: utf-8 -*-
"""02. 아이템 기반 협업 필터링

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1Si2r596uhHl-oWiyOi5frKR3GtgkZGYf
"""

from google.colab import drive
drive.mount('/content/drive')

import warnings
warnings.filterwarnings('ignore')

MOVIE_FILE_PATH = "/content/drive/MyDrive/한경_토스뱅크_2024/01_Machine Learning/05_추천시스템/data/ml-latest-small/movies.csv"
RATING_FILE_PATH = "/content/drive/MyDrive/한경_토스뱅크_2024/01_Machine Learning/05_추천시스템/data/ml-latest-small/ratings.csv"

import pandas as pd

movies = pd.read_csv(MOVIE_FILE_PATH)
ratings = pd.read_csv(RATING_FILE_PATH)

movies.head()

ratings.head()

rating_movies = pd.merge(ratings, movies, on='movieId')
rating_movies.head()

"""# 사용자-영화 희소 행렬
Pivot을 통해 사용자-아이템 행렬로 변환(희소행렬)
- 희소행렬 : 대부분의 값이 비어 있는 행렬..
- 모든 사용자가 모든 영화에 대해 평점을 부여하진 않는다.
"""

ratings_matrix = rating_movies.pivot_table("rating", index="userId", columns="title")
ratings_matrix.head()

# NaN값을 모두 0으로 변환 -> NaN이 있으면 유사도를 구할 수가 없다.
ratings_matrix = ratings_matrix.fillna(0)
ratings_matrix

"""# 영화-영화 유사도
사용자-영화 행렬을 전치하여 영화-사용자 행렬로 만든 다음 유사도 구하기
"""

ratings_matrix_T = ratings_matrix.T
ratings_matrix_T.head()

# 코사인 유사도 구하기
from sklearn.metrics.pairwise import cosine_similarity
item_sim = cosine_similarity(ratings_matrix_T, ratings_matrix_T)

# 유사도 행렬을 데이터 프레임으로 만들기
item_sim_df = pd.DataFrame(data=item_sim, index=ratings_matrix.columns, columns=ratings_matrix.columns)
item_sim_df

item_sim_df['[REC] (2007)'].sort_values(ascending=False)[:10]

"""# 평점 예측
- 아이템 기반 유사도 협업 필터링으로 개인화된 영화 추천

$$
\hat{R}_{u, i}=\frac{\sum\big{(}S_{i,N} \cdot R_{u,N}\big{)}}{\sum\big{(}\big{|}S_{i,N}\big{|}\big{)}}
$$
"""

import numpy as np

def predict_rating(ratings_arr, item_sim_arr):
  ratings_pred = ratings_arr @ item_sim_arr / np.array([np.abs(item_sim_arr).sum(axis=1)])

  return ratings_pred

ratings_matrix.shape, item_sim.shape

ratings_pred = predict_rating(ratings_matrix.values, item_sim_df.values)

ratings_pred_df = pd.DataFrame(
    data=ratings_pred,
    index=ratings_matrix.index,
    columns=ratings_matrix.columns
)

ratings_pred_df

"""# 예측 평가
가중치 평점 부여 후에 예측 성능 평가에 대한 MSE 구하기
"""

ratings_pred.nonzero()

# 실제 평점 데이터 중 원래 값이 들어있던 위치 구하기 -> target
# 예측 평점 데이터 중 실제 값이 들어있었던 위치의 값과 MSE를 계산
from sklearn.metrics import mean_squared_error

# 사용자가 평점을 부여한 영화에 대하서만 예측 성능 평가 MSE 구하기
def get_mse(pred, actual):
  # 실제 사용자가 평점을 부여한 위치의 데이터 (target)
  actual_y = actual[actual.nonzero()].flatten()

  # 실제 사용자가 평점을 부여한 위치의 예측 데이터 (pred)
  predict_y = pred[actual.nonzero()].flatten()

  return mean_squared_error(predict_y, actual_y)

get_mse(ratings_pred, ratings_matrix.values)

"""단순하게 유저-아이템 행렬과 아이템-아이템 유사도 행렬로 가중 평균 계산을 하면, **유사 하지 않은 아이템들도** 평점 예측에 참여하기 때문에 예측 평점이 낮을 수 밖에 없다."""

# top-n 유사도를 가진 데이터들에 대해서만 예측 평점 계산
def predict_rating_topsim(ratings_arr, item_sim_arr, n=20):
  # 사용자-아이템 평점 행렬 크기만큼 0으로 채운 예측 행렬 초기화
  pred = np.zeros(ratings_arr.shape)

  # 사용자-아이템 평점 행렬의 열 크기(영화의 개수)만큼 반복 수행
  for col in range(ratings_arr.shape[1]):
    # col 번째 영화와, 다른 모든 영화들 간의 유사도
    sim_items = item_sim_arr[:, col]
    top_n_items = [np.argsort(sim_items)[:-n-1:-1]]

    # 개인화된 예측 평점 계산
    for row in range(ratings_arr.shape[0]):
      # item_sim_arr[col, :][top_n_items] : col 번째 영화와 가장 유사도가 높은 top_n개 영화의 유사도
      # ratings_arr[row, :][top_n_items].T : row 번째 사람이 부여한 유사도가 가장 높은 top_n 영화에 대한 점수
      pred[row, col] = item_sim_arr[col, :][top_n_items] @ ratings_arr[row, :][top_n_items].T
      pred[row, col] /= np.sum(np.abs(item_sim_arr[col, :][top_n_items]))

  return pred

ratings_pred = predict_rating_topsim(ratings_matrix.values, item_sim_df.values)

get_mse(ratings_pred, ratings_matrix.values)

ratings_pred_matrix = pd.DataFrame(data=ratings_pred, index=ratings_matrix.index, columns=ratings_matrix.columns)
ratings_pred_matrix

"""# 추천시스템 작동"""

target_user_id = 78

# taget_user_id에 대한 모든 영화 정보
user_rating_id = ratings_matrix.loc[target_user_id, :]

# target_user_id가 평점을 부여한 영화 확인
user_rating_id[ user_rating_id > 0 ].sort_values(ascending=False)[:10]

"""사용자가 보지 않은 영화 중에서 아이템 기반의 유사도 협업 필터링 추천"""

def get_unseen_movies(ratings_matrix, userId):

  # userId로 입력 받은 사용자의 모든 영화 정보 추출.
  user_rating = ratings_matrix.loc[userId, :]

  # 이미 본 영화에 대한 인덱스 추출(영화 제목)
  already_seen = user_rating[ user_rating > 0 ].index.tolist()

  movie_list = ratings_matrix.columns.tolist()

  unseen_list = [ movie for movie in movie_list if movie not in already_seen ]

  return unseen_list

def recomm_movie_by_userId(pred_df, userId, unseen_list, top_n=10):
  recomm_movies = pred_df.loc[userId, unseen_list].sort_values(ascending=False)[:top_n]
  return recomm_movies

# 사용자가 관람하지 않은 영화명 추출
unseen_list = get_unseen_movies(ratings_matrix, 90)

# 추천 목록 만들기
recomm_movies = recomm_movie_by_userId(ratings_pred_matrix, target_user_id, unseen_list, top_n=10)

# 평점 데이터를 DataFrame으로
recomm_movies_df = pd.DataFrame(data=recomm_movies.values, index=recomm_movies.index, columns=["pred_score"])
recomm_movies_df

