# coding: utf-8
# YYeTsBot - bot.py
# 2019/8/15 18:27

__author__ = 'Benny <benny.think@gmail.com>'

import io
import time
import re
import os
import logging
import json
import tempfile

from urllib.parse import quote_plus

import telebot
from telebot import types, apihelper
from tgbot_ping import get_runtime

from html_request import get_search_html, analyse_search_html, get_detail_page
from utils import save_dump, save_to_cache, get_from_cache
from config import PROXY, TOKEN, SEARCH_URL, MAINTAINER

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(filename)s [%(levelname)s]: %(message)s')
if PROXY:
    apihelper.proxy = {'https': PROXY}

bot = telebot.TeleBot(os.environ.get('TOKEN') or TOKEN)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, '欢迎使用，发送想要的剧集标题，我会帮你搜索。\n'
                                      '人人影视倾向于欧美日韩剧集，请不要反馈“我搜不到喜羊羊与灰太狼”这种问题😠。\n'
                                      '建议使用<a href="http://www.zmz2019.com/">人人影视</a> 标准译名',
                     parse_mode='html', disable_web_page_preview=True)


@bot.message_handler(commands=['help'])
def send_help(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, '''机器人无法使用或者报错？你可以使用如下方式寻求使用帮助和报告错误：\n
    1. @BennyThink
    2. <a href='https://github.com/BennyThink/YYeTsBot/issues'>Github issues</a>
    3. <a href='https://t.me/mikuri520'>Telegram Channel</a>''', parse_mode='html', disable_web_page_preview=True)


@bot.message_handler(commands=['ping'])
def send_ping(message):
    bot.send_chat_action(message.chat.id, 'typing')
    info = get_runtime("botsrunner_yyets_1")
    bot.send_message(message.chat.id, info, parse_mode='markdown')


@bot.message_handler(commands=['credits'])
def send_credits(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, '''感谢字幕组的无私奉献！本机器人资源来源:\n
    <a href="http://www.zmz2019.com/">人人影视</a>
    <a href="http://oabt005.com/home.html">磁力下载站</a>
    <a href="http://www.zhuixinfan.com/main.php">追新番</a>
    ''', parse_mode='html')


def download_to_io(photo):
    logging.info("Initializing bytes io...")
    mem = io.BytesIO()
    file_id = photo[-1].file_id
    logging.info("Downloading photos...")
    file_info = bot.get_file(file_id)
    content = bot.download_file(file_info.file_path)
    mem.write(content)
    logging.info("Downloading complete.")
    return mem


def send_my_response(message):
    bot.send_chat_action(message.chat.id, 'record_video_note')
    # I may also send picture
    photo = message.photo
    uid = message.reply_to_message.caption
    text = f"主人说：{message.text or message.caption or '啥也没说😯'}"
    if photo:
        bot.send_chat_action(message.chat.id, 'typing')
        logging.info("Photo received from maintainer")
        mem = download_to_io(photo)
        mem.name = f'{uid}.jpg'
        r = bot.send_photo(uid, mem.getvalue(), caption=text)
    else:
        r = bot.send_message(uid, text)

    logging.info("Reply has been sent to %s with message id %s", uid, r.message_id)
    bot.reply_to(message, "回复已经发送给这位用户")
    fw = bot.forward_message(message.chat.id, uid, r.message_id)
    time.sleep(3)
    bot.delete_message(message.chat.id, fw.message_id)
    logging.info("Forward has been deleted.")


@bot.message_handler(content_types=["photo", "text"])
def send_search(message):
    if message.reply_to_message and message.reply_to_message.document and \
            message.reply_to_message.document.file_name == 'error.txt' and str(message.chat.id) == MAINTAINER:
        send_my_response(message)
        return
    bot.send_chat_action(message.chat.id, 'record_video')

    name = message.text
    if name is None:
        with open('assets/warning.webp', 'rb') as sti:
            bot.send_message(message.chat.id, "不要调戏我！我会报警的")
            bot.send_sticker(message.chat.id, sti)
        return

    logging.info('Receiving message about %s from user %s(%s)', name, message.chat.username, message.chat.id)
    html = get_search_html(name)
    result = analyse_search_html(html)

    markup = types.InlineKeyboardMarkup()
    for url, detail in result.items():
        btn = types.InlineKeyboardButton(detail['name'], callback_data="choose%s" % url)
        markup.add(btn)

    if result:
        bot.send_message(message.chat.id, "呐，💐🌷🌹选一个呀！", reply_markup=markup)
    else:
        bot.send_chat_action(message.chat.id, 'typing')

        encoded = quote_plus(name)
        bot.send_message(message.chat.id, f"没有找到你想要的信息🤪\n莫非你是想调戏我哦，😏\n\n"
                                          f"你先看看这个链接有没有结果。 {SEARCH_URL.format(kw=encoded)} "
                                          "如果有的话，那报错给我吧", reply_markup=markup, disable_web_page_preview=True)
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton("快来修复啦", callback_data="fix")
        markup.add(btn)
        bot.send_chat_action(message.chat.id, 'upload_document')
        bot.send_message(message.chat.id, f"《{name}》😭😭😭\n机器人不好用了？点下面的按钮叫 @BennyThink 来修！"
                                          f"⚠️别乱点啊，看好自己搜的是什么，不乖的话我可是会报警的哦。",
                         reply_markup=markup)
        content = f""" 报告者：{message.chat.first_name}@{message.chat.username}({message.chat.id})
                        问题发生时间：{time.strftime("%Y-%m-%data %H:%M:%S", time.localtime(message.date))}
                        请求内容：{name} 
                        请求URL：{SEARCH_URL.format(kw=encoded)}\n\n
                        返回内容：{html}
                    """
        save_dump(content)


@bot.callback_query_handler(func=lambda call: re.findall(r"choose(\S*)", call.data))
def choose_link(call):
    bot.send_chat_action(call.message.chat.id, 'typing')
    # call.data is url, http://www.rrys2020.com/resource/36588
    resource_url = re.findall(r"choose(\S*)", call.data)[0]

    link = get_from_cache(resource_url)
    if not link:
        link = get_detail_page(resource_url)
        save_to_cache(resource_url, link)

    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("分享页面", callback_data="share%s" % resource_url)
    btn2 = types.InlineKeyboardButton("我全都要", callback_data="all%s" % resource_url)
    markup.add(btn1, btn2)
    text = "想要分享页面，还是我全都要？\n\n" \
           "名词解释：“分享页面”会返回给你一个网站，从那里可以看到全部的下载链接。\n" \
           "“我全都要”会给你发送一个txt文件，文件里包含全部下载连接\n"
    bot.send_message(call.message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: re.findall(r"share(\S*)", call.data))
def share_page(call):
    bot.send_chat_action(call.message.chat.id, 'typing')
    resource_url = re.findall(r"share(\S*)", call.data)[0]
    result = get_from_cache(resource_url)
    bot.send_message(call.message.chat.id, result['share'])


@bot.callback_query_handler(func=lambda call: re.findall(r"all(\S*)", call.data))
def all_episode(call):
    # just send a file
    bot.send_chat_action(call.message.chat.id, 'typing')
    resource_url = re.findall(r"all(\S*)", call.data)[0]
    result = get_from_cache(resource_url)

    with tempfile.NamedTemporaryFile(mode='wb+', prefix=result["cnname"], suffix=".txt") as tmp:
        bytes_data = json.dumps(result["all"], ensure_ascii=False, indent=4).encode('u8')
        tmp.write(bytes_data)

        with open(tmp.name, "rb") as f:
            bot.send_chat_action(call.message.chat.id, 'upload_document')
            bot.send_document(call.message.chat.id, f)


@bot.callback_query_handler(func=lambda call: call.data == 'fix')
def report_error(call):
    logging.error("Reporting error to maintainer.")
    bot.send_chat_action(call.message.chat.id, 'typing')
    bot.send_message(MAINTAINER, '人人影视机器人似乎出现了一些问题🤔🤔🤔……')
    debug = open(os.path.join(os.path.dirname(__file__), 'data', 'error.txt'), 'r', encoding='u8')
    bot.send_document(MAINTAINER, debug, caption=str(call.message.chat.id))
    bot.answer_callback_query(call.id, 'Debug信息已经发送给维护者，请耐心等待修复~', show_alert=True)
    # bot.edit_message_text("好了，信息发过去了，坐等回复吧！", call.message.chat.id, call.message.message_id)


if __name__ == '__main__':
    logging.info('YYeTs bot is running...')
    bot.polling(none_stop=True, )
