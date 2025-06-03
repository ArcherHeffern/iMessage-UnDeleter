# iMessage deleted chat recovery tool
## Purpose
This is a program to notify you when a messages was deleted from a targeted iMessage conversation and report what the message was.  

Credits for reversing the iMessage API goes to [@yortos](https://github.com/yortos/imessage-analysis). Read his [blog post](https://medium.com/@yaskalidis/heres-how-you-can-access-your-entire-imessage-history-on-your-mac-f8878276c6e9) on how it works! Even though the code itself has since been updated, the base code and process is the same.  
* No credit goes to him for the recovery of deleted messages idea, I don't think he's scary like that  

I modified the code to 
* Only fetch one conversation, instead of everything, greatly speeding up the process. 
* Watch the iMessage database file and compare for differences from last time we recieved a message
* Notify me whenever a deleted message was detected

Let me know if this is unethical in the github issues tab.

## DataFrame Columns and Descriptions
Starting from the end, here's the dataframe the `get_chat` function produces. 


| Column Name               | Type         | Description                                            |
|---------------------------|--------------|--------------------------------------------------------|
| `message_id`              | integer  |   Unique ID for this message       |
| `is_from_me`              | bool  | |
| `text_combined`           | Optional[string]  | The most complete data I could find for the text of the message. If `text` (see below) is NULL then this takes the value of `inferred_text`, otherwise `text`. This is because `text` is the field from Apple but it can be NULL often, in which case I resort to hacky methods to infer the text. |
| `text`                    | Optional[string]  | The text of the message, native from Apple.            |
| `inferred_text`           | Optional[string]  | If the `text` value above is NULL, I try and infer the text from the field called `attributedBody` which can be found in the messages database. This process is not perfect, and currently works only for English.    |
| `timestamp`               | pd.Timestamp  | The timestamp when the message was sent. When storing the dataframe in CSV and loading again the type resets to string. Convert to timestamp with `pd.Timestamp(x)`. Example value: '2024-04-26 14:35:03'|
| `is_audio_message`        | bool  | |
| `message_effect`          | string  | The effect that the message was sent with, or `no-effect` if there is none. Possible values: `impact`, `gentle`, `Echo`, `HappyBirthday`, `loud`, `Fireworks`, `Lasers`, `invisibleink`, `Confetti`, `Heart`, `Spotlight`, `Sparkles`, `ShootingStar` |
| `reaction`                | string  |  The type of reaction that this message is, or `no-reaction` if it is not a reaction. Possible values: `Disliked`, `Emphasized`, `Laughed`, `Liked`, `Loved`, `Questioned`, `Removed dislike`, `Removed emphasis`, `Removed heart`, `Removed laugh`, `Removed like`, `Removed question mark`       |
| `is_thread_reply`         | bool  | Indicates whether this message was a reply to a specific message (i.e,, a thread) or not. |


## Getting Started
You need a Mac for this process.

1. Create a .env using `sample.env`
* Phone number must be of the format: `+12345678901`. 
2. Enable `Privacy & Security > Full Disk Access` for the terminal you will use to run this program
* This is because accessing the messages database requires full disk access
3. Install dependencies using `pip install -r requirements.txt`
4. Run `python3.13 main.py`


[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
## License

This project is licensed under the [Creative Commons Attribution-NonCommercial 4.0 International License](https://creativecommons.org/licenses/by-nc/4.0/).
