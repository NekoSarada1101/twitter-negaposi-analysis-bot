import requests
import json
import emoji
import os
from setting_secret import *
from wordcloud import WordCloud
from google.cloud import language_v1
from google.cloud import storage

language_client = language_v1.LanguageServiceClient.from_service_account_file("credentials.json")
storage_client = storage.Client.from_service_account_json("credentials.json")
bucket = storage_client.get_bucket('slackbot-288310.appspot.com')


def do_post(e: requests) -> str:
    if SLACK_TOKEN != e.form.get("token"):
        raise Exception("not allowed verification token")

    keyword = e.form.get("text")
    tweet_list = fetch_tweet_list(keyword)  # type: list

    noun_list = []  # type: list
    tweet_score = 0  # type: int

    for index in range(len(tweet_list)):
        text = remove_emoji(tweet_list[index]["text"])  # type: str
        # ネガポジ度を取得
        score = fetch_sentiment_score(text)  # type: int
        tweet_score += score
        # 名詞を抽出
        noun_list.extend(extract_noun(text))

    tweet_score /= len(tweet_list)

    create_word_cloud(noun_list)

    data = {  # type: json
        "attachments": [
            {
                "color": "FFFFFF",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "ネガポジ判定ワード：" + keyword
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "ネガポジ度：" + str(tweet_score)
                        }
                    },
                    {
                        "type": "image",
                        "image_url": "https://storage.googleapis.com/slackbot-288310.appspot.com/wc_image_ja.png",
                        "alt_text": "wordCloud"
                    }
                ]
            }
        ]
    }

    payload = json.dumps(data).encode("utf-8")  # type: json
    requests.post(HISHO_URL, payload)
    return ""


def fetch_tweet_list(keyword: str) -> list:
    max_results = 10  # type: int
    endpoint_url = "https://api.twitter.com/2/tweets/search/recent?query={}&max_results={}".format(keyword, str(
        max_results))  # type: str
    header = {  # type: dict
        "Authorization": "Bearer " + BEARER_KEY
    }
    response = requests.get(url=endpoint_url, headers=header)  # type: response
    tweet_list = json.loads(response.text)["data"]  # type: list
    return tweet_list


def remove_emoji(src_str: str) -> str:
    return ''.join(c for c in src_str if c not in emoji.UNICODE_EMOJI)


def fetch_sentiment_score(text: str) -> int:
    document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)  # type: document
    sentiment = language_client.analyze_sentiment(request={'document': document})  # type: json
    return sentiment.document_sentiment.score


def extract_noun(text: str) -> list:
    noun_list = []
    document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
    syntax = language_client.analyze_syntax(request={'document': document})  # type: json
    for token in syntax.tokens:
        part_of_speech = token.part_of_speech  # type: json
        if language_v1.PartOfSpeech.Tag(part_of_speech.tag).name == "NOUN":  # もし名詞なら
            noun_list.append(token.text.content)
    return noun_list


def create_word_cloud(noun_list: list):
    download_font_file()

    font_path = "/tmp/ヒラギノ角ゴシック W3.ttc"
    stop_words = ["RT", "@", ":/", 'もの', 'こと', 'とき', 'そう', 'たち', 'これ', 'よう', 'これら', 'それ', 'すべて']
    word_chain = ' '.join(noun_list)
    word_cloud = WordCloud(background_color="white", font_path=font_path, contour_color='steelblue', collocations=False,
                           contour_width=3, width=900, height=500, stopwords=set(stop_words)).generate(word_chain)
    word_cloud.to_file("/tmp/wc_image_ja.png")
    upload_word_cloud_image()


def download_font_file():
    if os.path.exists('/tmp/ヒラギノ角ゴシック W3.ttc') is False:
        print("Download FontFile")
        try:
            # GCSにあるダウンロードしたいファイルを指定
            blob = bucket.blob("ヒラギノ角ゴシック W3.ttc")
            # ファイルとしてローカルに落とす
            blob.download_to_filename("/tmp/ヒラギノ角ゴシック W3.ttc")
        except Exception as exception:
            print(exception)


def upload_word_cloud_image():
    if os.path.exists('/tmp/wc_image_ja.png') is True:
        print("Upload ImageFile")
        try:
            # 格納するGCSのPathを指定
            blob = bucket.blob("wc_image_ja.png")
            # ファイルとしてCloud Storageにアップロード
            blob.upload_from_filename("/tmp/wc_image_ja.png")
        except Exception as exception:
            print(exception)


if __name__ == '__main__':
    do_post()
