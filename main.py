from datetime import datetime
from pathlib import Path
from sqlite3 import connect
import sys
from time import sleep
from typing import Optional

import pandas as pd
from dotenv import dotenv_values
from pandera.pandas import DataFrameModel, Field
from pandera.typing import DataFrame, Series

import helper as hp


def eprint(msg):
    """
    Prints to stderr
    """
    print(msg, file=sys.stderr)


ENV = dotenv_values()
DEBUG = True
TARGET_EMAIL_OR_PHONE_NUMBER = ENV["TARGET_EMAIL_OR_PHONE_NUMER"]
IMESSAGE_FILE = f"{Path.home()}/Library/Messages/chat.db"
LOGFILE = "LOGFILE"

if not TARGET_EMAIL_OR_PHONE_NUMBER:
    eprint("Fill out your .env!")
    sys.exit(1)


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


def get_chat(
    imessage_file,
    target_email_or_phone_number: str,
    last_n: Optional[int] = None,
    filter_your_messages: bool = False,
) -> DataFrame[MessagesSchema]:
    conn = connect(imessage_file)

    with conn as cur:
        handle = cur.execute(
            "select * from handle WHERE id=? AND service=='iMessage'",
            (target_email_or_phone_number,),
        ).fetchone()
        if handle is None:
            print("Failed to fetch handle_id")
            sys.exit(1)
        handle_id = handle[0]

    limit = ""
    if last_n:
        limit = f"LIMIT {last_n}"
    filter_your_messages_query = ""
    if filter_your_messages:
        filter_your_messages_query = "AND is_from_me=0"
    messages = pd.read_sql_query(
        f"""select *,
        datetime(date/1000000000 + strftime("%s", "2001-01-01") ,"unixepoch","localtime") as date_utc 
        FROM message 
        WHERE handle_id=? 
        {filter_your_messages_query}
        ORDER BY date DESC {limit}""",
        conn,
        params=(handle_id,),
    )
    messages.rename(columns={"ROWID": "message_id"}, inplace=True)

    messages["inferred_text"] = messages["attributedBody"].apply(
        lambda x: hp.clean_text(x)
    )
    messages["text_combined"] = messages.apply(
        lambda row: row["inferred_text"] if pd.isnull(row["text"]) else row["text"],
        axis=1,
    )
    messages["message_effect"] = messages["expressive_send_style_id"].apply(
        lambda x: hp.detect_message_effect(x)
    )
    messages["is_thread_reply"] = (~messages["thread_originator_guid"].isnull()).astype(
        int
    )
    messages["reaction"] = messages["associated_message_type"].apply(
        lambda x: hp.detect_reaction(x)
    )
    messages["timestamp"] = messages["date_utc"].apply(lambda x: pd.Timestamp(x))
    # removing '\r' from the text of the messages as they interfere with the to_csv command.
    messages["text"] = messages["text"].str.replace("\r", "")
    messages["text_combined"] = messages["text_combined"].str.replace("\r", "")
    messages["inferred_text"] = messages["inferred_text"].str.replace("\r", "")

    columns = [
        "message_id",
        "is_from_me",
        "text_combined",
        "text",
        "inferred_text",
        "timestamp",
        "is_audio_message",
        "message_effect",
        "reaction",
        "is_thread_reply",
    ]
    messages["is_from_me"] = messages["is_from_me"].apply(lambda x: bool(x))
    messages["is_audio_message"] = messages["is_audio_message"].apply(lambda x: bool(x))
    messages["is_thread_reply"] = messages["is_thread_reply"].apply(lambda x: bool(x))
    return MessagesSchema.validate(messages[columns])


def log_messages(messages: DataFrame[MessagesSchema]):
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"==={datetime.now()}===\n")
        for _, message in messages.iterrows():
            f.write(f">>> {message["timestamp"]}\n")
            f.write(f"\tText combined: {message["text_combined"]}\n")
            f.write(f"\tText: {message["text"]}\n")
            f.write(f"\tInferred Text: {message["inferred_text"]}\n")
            f.write(f"\tIs Audio Message: {message["is_audio_message"]}\n")
            f.write(f"\tMessage Effect: {message["message_effect"]}\n")
            f.write(f"\tReaction: {message["reaction"]}\n")
            f.write(f"\tIs Thread Reply: {message["is_thread_reply"]}\n")


print("Watching...")
last_messages = get_chat(IMESSAGE_FILE, TARGET_EMAIL_OR_PHONE_NUMBER, 2, True)

try:
    while True:
        new_messages = get_chat(IMESSAGE_FILE, TARGET_EMAIL_OR_PHONE_NUMBER, 2, True)
        if not last_messages.equals(new_messages):
            log_messages(last_messages)
            print("Difference noticed...")
        else:
            sleep(0.5)
        last_messages = new_messages
except KeyboardInterrupt:
    print("Exiting...")
