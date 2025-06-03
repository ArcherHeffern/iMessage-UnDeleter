from sqlite3 import connect
from sys import exit
import pandas as pd
import sys
import helper as hp
from pandera.typing import Series, DataFrame
from pandera.pandas import DataFrameModel
from pandera.pandas import Field
from dotenv import dotenv_values

def eprint(msg):
    print(msg, file=sys.stderr)

ENV = dotenv_values()
DEBUG = True
TARGET_EMAIL_OR_PHONE_NUMBER = ENV["TARGET_EMAIL_OR_PHONE_NUMER"]
HOME_DIRECTORY_USERNAME = ENV["HOME_DIRECTORY_USERNAME"]

if not TARGET_EMAIL_OR_PHONE_NUMBER or not HOME_DIRECTORY_USERNAME:
    eprint("Fill out your .env!")
    exit(1)

class MessagesSchema(DataFrameModel):
    message_id: Series[int]
    is_from_me: Series[bool]
    text_combined: Series[str] = Field(nullable=True)
    text: Series[str] = Field(nullable=True)
    inferred_text: Series[str] = Field(nullable=True)
    timestamp: Series[pd.Timestamp]
    is_audio_message: bool
    message_effect: str
    reaction: str
    is_thread_reply: bool

def get_chat(home_directory_username: str, target_email_or_phone_number: str) -> DataFrame[MessagesSchema]:
    conn = connect(f'/Users/{home_directory_username}/Library/Messages/chat.db')

    with conn as cur:
        handle = cur.execute("select * from handle WHERE id=? AND service=='iMessage'", (target_email_or_phone_number,)).fetchone()
        if handle is None:
            print("Failed to fetch handle_id")
            exit(1)
        handle_id = handle[0]

    messages = pd.read_sql_query('''select *, datetime(date/1000000000 + strftime("%s", "2001-01-01") ,"unixepoch","localtime")  as date_utc from message WHERE handle_id=? ORDER BY date DESC''', conn, params=(handle_id,)) 
    messages.rename(columns={'ROWID':'message_id'}, inplace=True)

    # table mapping each chat_id to the handles that are part of that chat.
    with conn as cur:
        chat_handle_join = cur.execute("select * from chat_handle_join WHERE handle_id=?", (handle_id,)).fetchone()
        chat_id, _ = chat_handle_join

    # table mapping each message_id to its chat_id
    chat_message_joins = pd.read_sql_query("select * from chat_message_join WHERE chat_id=?", conn, params=(chat_id,))

    messages = pd.merge(messages, chat_message_joins, how='left', on='message_id')
    messages['inferred_text'] = messages['attributedBody'].apply(lambda x: hp.clean_text(x))
    messages['text_combined'] = messages.apply(lambda row: row['inferred_text'] if pd.isnull(row['text']) else row['text'], axis=1)
    messages['message_effect'] = messages['expressive_send_style_id'].apply(lambda x: hp.detect_message_effect(x))
    messages['is_thread_reply'] = (~messages['thread_originator_guid'].isnull()).astype(int)
    messages['reaction'] = messages['associated_message_type'].apply(lambda x: hp.detect_reaction(x))
    messages['timestamp'] = messages['date_utc'].apply(lambda x: pd.Timestamp(x))
    # removing the special character '\r' from the text of the messages as they interfere with the to_csv command.
    messages['text'] = messages['text'].str.replace('\r', '')
    messages['text_combined'] = messages['text_combined'].str.replace('\r', '')
    messages['inferred_text'] = messages['inferred_text'].str.replace('\r', '')

    columns = ['message_id', 'is_from_me', 'text_combined', 'text', 'inferred_text', 'timestamp', 'is_audio_message', 'message_effect', 'reaction', 'is_thread_reply',]
    messages['is_from_me'] = messages['is_from_me'].apply(lambda x: bool(x))
    messages['is_audio_message'] = messages['is_audio_message'].apply(lambda x: bool(x))
    messages['is_thread_reply'] = messages['is_thread_reply'].apply(lambda x: bool(x))
    return MessagesSchema.validate(messages[columns])

df_messages = get_chat(HOME_DIRECTORY_USERNAME, TARGET_EMAIL_OR_PHONE_NUMBER)
# with pd.option_context('display.max_columns', None):
#     print(df_messages.head())