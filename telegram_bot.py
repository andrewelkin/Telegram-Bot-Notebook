import os, sys, shutil
import json
from telegram.ext import CommandHandler, filters, MessageHandler,  Application, ContextTypes
from telegram.constants import ParseMode
from telegram import Update
from functools import wraps
import time
import codecs
import re
import string

messages_path = "./"

"""
 File "secret.txt" contains a single line with secret code (access token) you received from the telegram bot father
 File "config.json" has "users" root entry with this format for each user:

 
 "<First> <Last>" {
  "id": <telegram user id>,
  "settings":  [,admin=1][,uploads=<subdir for personal uploads"] 
 }
 
  "John Doe": {
     "id": 123303756,
     "settings": "admin=1, uploads=JD_Uploads/"
   },


 only admins can delete messages and upload new ones. all plain users just search/view messages
 
 Note:
 with user's telegram id set to 0 the bot will accept any user with that user name. This is unsecure,
 and you should use this option only for the very first time. The bot will let the user in and print the telegram id.
 You should use that id and put it into the config entry for the user. 
 
 
"""

messages = []
new_messages = []
admins = {}
users = {}
pic_dir = {}
pic_files = []
all_tags = {}

max_messages_in_search = 10

user_settings = {}
user_session_settings = {}


def read_config(file_name):
    try:
        c = json.load(open(file_name))
    except Exception as e:
        print("Error reading config", e)
        return None

    return c


def read_users():
    global users, admins
    users = {}
    admins = {}
    for uname, user in cfg['users'].items():

        idd = user.get("id")
        if idd is None:
            idd = 0

        users[uname] = idd
        items = user.get("settings", "").split(",")

        settings = {}
        for i in items:
            j = i.strip().split("=")
            if len(j) == 2:
                if j[0] == "admin":
                    if j[1] == "1":
                        admins[uname] = idd
                        print("added admin '%s' with id %s" % (uname, idd))
                else:
                    settings[j[0].strip()] = j[1].strip()

        user_settings[uname] = settings

        print("added user '%s' with id %s " % (uname, idd), settings.items())
        user_session_settings[uname] = {}

    print("%d users known for the bot" % len(users))


def is_user_ok(first, last, uid):
    i = users.get("%s %s" % (first, last))
    if i is None:
        return False
    if i == 0:
        users["%s %s" % (first, last)] = uid
        print("Registered id %s for user %s %s" % (uid, first, last))
        return True

    return i == uid


def is_admin_ok(first, last, uid):
    i = admins.get("%s %s" % (first, last))
    if i is None:
        return False
    if i == 0:
        admins["%s %s" % (first, last)] = uid
        print("Registered id %s for admin %s %s" % (uid, first, last))
        return True

    return i == uid


def xis_user_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_ok(update.message.chat.first_name, update.message.chat.last_name,
                      update.message.chat.id):
        context.bot.send_message(
            chat_id=update.message.chat_id,
            text="<i>(.. You are not authorized to use this service.)</i>",
            parse_mode=ParseMode.HTML,
        )
        print(update.message.chat.first_name, update.message.chat.last_name, "not authorized for the service")
        return False

    return True


def xis_admin_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_ok(update.message.chat.first_name, update.message.chat.last_name,
                       update.message.chat.id):
        context.bot.send_message(
            chat_id=update.message.chat_id,
            text="<i>(.. You are not authorized for this operation.)</i>",
            parse_mode=ParseMode.HTML,
        )
        print(update.message.chat.first_name, update.message.chat.last_name, "not authorized for the op")
        return False

    return True


def build_pic_dir():
    global pic_dir, pic_files

    pic_files = []
    pic_dir = {}
    for m in messages:
        if m.startswith("/p#i#c"):
            m = m[7:]
            file_name = m.split(" ")[0]
            m = m[len(file_name) + 1:]
            pic_dir[file_name] = m

    pic_files = [s for s in os.listdir(pic_path) if s.lower().endswith(".jpg")]


def update_tags(m):
    # wordList = re.sub("[^#a-zA-Z0-9_]", " ", curr_message).split()
    sp = string.punctuation.replace("#", "")
    word_list = re.sub("[" + sp + "]", "", m).split()
    for w in word_list:
        if w.startswith("#") and len(w) > 1:
            l_tags = all_tags.setdefault(w, set())
            l_tags.add(len(messages) - 1)


def rebuild_tags():
    global messages, all_tags
    ms = messages
    messages = []
    all_tags = {}
    for m in ms:
        messages.append(m)
        update_tags(m)


def read_messages():
    global messages
    msg_name = messages_path + "notes.txt"
    if not os.path.exists(msg_name):
        return []
    # f = file(msg_name)
    f = codecs.open(msg_name, "r", "cp1251")
    all_s = f.read()

    messages = []
    curr_message = ""
    for s in all_s.split("\n"):
        s += "\n"
        if s.startswith("---"):
            if len(curr_message) == 0:
                continue
            messages.append(curr_message)
            update_tags(curr_message)
            curr_message = ""
            continue
        curr_message += s
    if len(curr_message) != 0:
        messages.append(curr_message)
        update_tags(curr_message)
    f.close()
    return messages


def update_messages():
    global new_messages
    for m in new_messages:
        messages.append(m)
        update_tags(m)

    new_messages = []


def save_messages():
    msg_name = messages_path + "notes.txt"
    # f = file(msg_name,'w')
    f = codecs.open(msg_name, "w", "cp1251")
    for s in messages:
        f.write("---\n")
        f.write(s)
        if not s.endswith("\n"):
            f.write("\n")
    f.close()


def send_action(action):
    """Sends `action` while processing func command."""

    def decorator(func):
        @wraps(func)
        def command_func(*args, **kwargs):
            bot = args[1].bot
            bot.send_chat_action(chat_id=args[0].message.chat_id, action=action)
            func(args[0], args[1], args[1].args)

        return command_func

    return decorator


async def hello(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await bot.message.reply_text(
        "Hello {}".format(bot.message.from_user.first_name)
        + ", I have %d notes" % (len(messages) + len(new_messages))
    )

    await del_u_settings(bot, context)


async def send_message(bot, context: ContextTypes.DEFAULT_TYPE, mess_no, full=False):
    if len(messages) < mess_no:
        await context.bot.send_message(
            chat_id=bot.message.chat_id,
            text="<i>(..could not find message %03d, max number is %d)</i> " % (mess_no,len(messages)),
            parse_mode=ParseMode.HTML,
        )
        return 

    m1 = messages[mess_no - 1]
    if m1.startswith("/d#o#c"):
        m1 = m1[7:]

        if m1.startswith('"'):
            file_name = m1[1:].split('"')[0].replace("\n", "")
        else:
            file_name = m1.split(" ")[0].replace("\n", "")

        if full:
            try:
                fo = open(doc_path + file_name, "rb")
                await context.bot.send_document(chat_id=bot.message.chat_id, document=fo)
                fo.close()
            except:
                await context.bot.send_message(
                    chat_id=bot.message.chat_id,
                    text="[%03d] <i>(..document is missing %s)</i> " % (mess_no, file_name),
                    parse_mode=ParseMode.HTML,
                )
        else:
            await context.bot.send_message(chat_id=bot.message.chat_id,
                                     text="[%03d] (%s) %s" % (mess_no, "document", file_name))

    elif m1.startswith("/p#i#c"):
        m1 = m1[7:]
        file_name = m1.split(" ")[0].replace("\n", "")
        m1 = m1[len(file_name) + 1:]

        if full:

            try:
                fo = open(pic_path + file_name, "rb")
                await context.bot.send_photo(chat_id=bot.message.chat_id, photo=fo, caption="[%03d] " % mess_no + m1)
                fo.close()
            except:
                await context.bot.send_message(
                    chat_id=bot.message.chat_id,
                    text="[%03d] <i>(..picture is missing %s)</i> " % (mess_no, m1),
                    parse_mode=ParseMode.HTML,
                )

        else:

            await context.bot.send_message(chat_id=bot.message.chat_id, text="[%03d] (%s)" % (mess_no, "picture") + m1)

    else:
        await context.bot.send_message(chat_id=bot.message.chat_id, text="[%03d] " % mess_no + m1)


def scan1dir4docs(p):
    res = []
    d = os.listdir(p)
    for od in d:
        if os.path.isdir(p + od):
            res += scan1dir4docs(p + od + "/")
        else:
            res.append(p + od)
    return res


def scan4docs(path):
    n = len(path)
    res = [d[n:] for d in scan1dir4docs(path)]
    # for d in res :
    #    print d
    return res


# @send_action(ChatAction.TYPING)
async def all_docs(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    res = scan4docs(doc_path)
    s = set()
    for m in messages:
        if m.startswith("/d#o#c"):
            m = m[7:]
            if m.startswith('"'):
                file_name = m[1:].split('"')[0]
            else:
                file_name = m.split(" ")[0]

            s.add(file_name.replace("\n", ""))

    for r in res:
        if r not in s:
            if r.find(" ") >= 0:
                m = '/d#o#c "%s"' % r
            else:
                m = "/d#o#c %s" % r

            new_messages.append(m)

    update_messages()  ## debug
    save_messages()  ## debug

    args = [s1 for s1 in bot.message.text.split() if len(s1) > 0]
    if len(args) == 1:
        args = ["/f","d#o#c"]
        await actual_find_substring(bot, context, args)
    else:
        args = ["/f","+d#o#c"] + bot.message.text.split()
        await actual_find_substring(bot, context, args)


# @send_action(ChatAction.TYPING)
async def find_substring(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not xis_user_ok(bot, context):
        return

    args = [s1 for s1 in bot.message.text.split() if len(s1) > 0]
    if len(args) <2:
        await bot.message.reply_text(
            "Please use syntax:  /f [+<must_be_sub_string1> ..] [!<must_not_be_sub_string1> ..] [<substring1> ..]  "
        )
        return
    await actual_find_substring(bot,context, args)


async def actual_find_substring(bot: Update, context: ContextTypes.DEFAULT_TYPE, args) -> None:

    included = []
    excluded = []
    must_be = []
    anything = False

    done = 0
    for s in args[1:]:

        s = s.replace("'", "")
        s = s.replace('"', "")

        if s.startswith("!"):
            excluded.append(s[1:].lower())
        elif s.startswith("+"):
            must_be.append(s[1:].lower())
        else:
            included.append(s.lower())

    mess_no = 0
    for m1 in messages:
        mess_no += 1
        m = m1.lower()
        need_break = False
        for e in excluded:
            if m.find(e) >= 0:
                need_break = True
                break
        if need_break:
            continue
        for o in must_be:
            if m.find(o) < 0:
                need_break = True
                break
        if need_break:
            continue

        maybe = False  ##if len(must_be)==0 else True
        if not maybe:
            for o in included:
                if m.find(o) >= 0:
                    maybe = True
                    break
        if maybe:
            done += 1
            if done >= max_messages_in_search:
                await context.bot.send_message(
                    chat_id=bot.message.chat_id,
                    text="<i>(.. there are more notes in search, please rectify.)</i>",
                    parse_mode=ParseMode.HTML,
                )
                break

            anything = True
            await send_message(bot, context, mess_no)

    if not anything:
        await context.bot.send_message(
            chat_id=bot.message.chat_id, text="<i>(.. there are no matches.)</i>", parse_mode=ParseMode.HTML
        )


async def refresh(_: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("Refreshing..")
    global messages, new_messages
    read_messages()
    new_messages = []
    read_users()
    build_pic_dir()


## exit()

# @send_action(ChatAction.TYPING)
async def del_message(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not xis_admin_ok(bot, context):
        return

    args = [s1 for s1 in bot.message.text.split() if len(s1) > 0]
    if len(args) < 2:
        await context.bot.send_message(
            chat_id=bot.message.chat_id,
            text="<i>(.. Please specify at least one message number.)</i>",
            parse_mode=ParseMode.HTML,
        )

        return

    to_del = set()
    for a1 in args[1:]:
        i = int(a1) - 1
        if i >= len(messages):
            continue
        print("Deleting message no %d" % i)

        m = messages[i]
        if m.startswith("/d#o#c"):
            m = m[7:]
            if m.startswith('"'):
                file_name = m[1:].split('"')[0].replace("\n", "")
            else:
                file_name = m.split(" ")[0].replace("\n", "")

            try:
                os.unlink(doc_path + file_name)
                print("Deleted file ", doc_path + file_name)
            except:

                print("Could not delete ", doc_path + file_name)

        to_del.add(i)

    to_del = list(to_del)
    to_del.sort()
    to_del.reverse()

    repl = ""
    for td in to_del:
        repl += "<i>(..message #%d deleted)</i>\n" % (td + 1)
        del messages[td]

    if repl != "":
        await context.bot.send_message(chat_id=bot.message.chat_id, text=repl, parse_mode=ParseMode.HTML)

    save_messages()  ## debug
    rebuild_tags()
    build_pic_dir()


async def unknown_cmd(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    txt = bot.message.text
    if txt is not None and len(txt) > 1:
        txt = txt[1:]
        if txt[0] == "#":
            await find_tag(bot, context)
            return

        if txt.isdigit():
            num = int(txt)
            await send_message(bot, context, num, True)
            return
        else:
            args = ["/f"] + txt.split()
            await actual_find_substring(bot, context, args)
            return

    await context.bot.send_message(chat_id=bot.message.chat_id, text="Sorry, I didn't understand that command:  " + txt)


# @send_action(ChatAction.TYPING)
async def get_pic(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not xis_user_ok(bot, context):
        return
    ndx = 0
    args = [s1 for s1 in bot.message.text.split() if len(s1) > 0]
    if len(args) > 1:
        ndx = int(args[1]) - 1
    else:
        await context.bot.send_message(
            chat_id=bot.message.chat_id,
            text="<i>(..please define picture number)</i> ",
            parse_mode=ParseMode.HTML,
        )
        return

    if ndx <0 or ndx >= len(pic_files):
        await context.bot.send_message(
            chat_id=bot.message.chat_id,
            text="<i>(.. Photo #%d not found.)</i>" % (ndx + 1),
            parse_mode=ParseMode.HTML,
        )
        return

    file_name = pic_files[ndx]
    capt = pic_dir.get(file_name, file_name)
    capt = "[pic %03d] " % (ndx + 1) + capt

    try:
        fo = open(pic_path + file_name, "rb")
        await context.bot.send_photo(chat_id=bot.message.chat_id, photo=fo, caption=capt)
    except:
        await context.bot.send_message(
            chat_id=bot.message.chat_id,
            text="<i>(..picture #%d is missing)</i> " % (ndx + 1),
            parse_mode=ParseMode.HTML,
        )


async def del_pic(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not xis_admin_ok(bot, context):
        return
    args = [s1 for s1 in bot.message.text.split() if len(s1) > 0]
    if len(args) < 2:
        await context.bot.send_message(
            chat_id=bot.message.chat_id,
            text="<i>(.. Please specify at least one picture number.)</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    ndx = int(args[1]) - 1
    if ndx >= len(pic_files):
        await context.bot.send_message(
            chat_id=bot.message.chat_id,
            text="<i>(.. Photo #%d not found.)</i>" % (ndx + 1),
            parse_mode=ParseMode.HTML,
        )
        return

    if pic_files[ndx] == "(..deleted)":
        await context.bot.send_message(
            chat_id=bot.message.chat_id,
            text="<i>(..picture #%d is already deleted)</i> " % (ndx + 1),
            parse_mode=ParseMode.HTML,
        )
        return

    file_name = pic_files[ndx]

    try:
        os.unlink(pic_path + file_name)
        await context.bot.send_message(
            chat_id=bot.message.chat_id,
            text="<i>(..picture #%d deleted)</i> " % (ndx + 1),
            parse_mode=ParseMode.HTML,
        )
        pic_files[ndx] = "(..deleted)"
    except:
        await context.bot.send_message(
            chat_id=bot.message.chat_id,
            text="<i>(..picture #%d is missing)</i> " % (ndx + 1),
            parse_mode=ParseMode.HTML,
        )


# @send_action(ChatAction.TYPING)
async def find_tag(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not xis_user_ok(bot, context):
        return
    args = [s1 for s1 in bot.message.text.split() if len(s1) > 0]
    if len(args) == 1 and len(args[0]) >1 and (args[0][0] == '#' or args[0].startswith('/#')) :
        tg = args[0][1:]
        if tg[0] == '#':
            tg = tg[1:]
        args =["/tag", tg]

    if len(args) < 2:
        await context.bot.send_message(
            chat_id=bot.message.chat_id, text="<i>(.. Please specify tag.)</i>", parse_mode=ParseMode.HTML
        )
        return

    t = args[1]
    if not t.startswith("#"):
        t = "#" + t
    l_tags = all_tags[t]
    if l_tags is None:
        await context.bot.send_message(chat_id=bot.message.chat_id, text="<i>(..tag is not found)</i> ",
                                 parse_mode=ParseMode.HTML)
        return

    ll = list(l_tags)
    ll.sort()
    for ndx in ll[:10]:
        await send_message(bot, context, ndx + 1, len(ll) == 1)


# @send_action(ChatAction.TYPING)
async def tags_dir(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not xis_user_ok(bot, context):
        return

    rep = "<i>(.. tags found: %d)</i>\n" % len(all_tags)

    for k, l in all_tags.items():
        rep += "%s (%d)," % (k, len(l))

    if len(rep) > 0:
        rep = rep[: len(rep) - 1]

    await context.bot.send_message(chat_id=bot.message.chat_id, text=rep, parse_mode=ParseMode.HTML)


# @send_action(ChatAction.TYPING)
async def del_u_settings(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not xis_user_ok(bot, context):
        return
    nm = "%s %s" % (bot.message.from_user.first_name, bot.message.from_user.last_name)
    user_session_settings[nm] = {}
    await context.bot.send_message(
        chat_id=bot.message.chat_id,
        text="<i>(.. session level user settings deleted.)</i>",
        parse_mode=ParseMode.HTML,
    )


# @send_action(ChatAction.TYPING)
async def show_settings(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not xis_user_ok(bot, context):
        return

    nm = "%s %s" % (bot.message.from_user.first_name, bot.message.from_user.last_name)
    ss = user_session_settings.get(nm)

    m = "<i>Session active settings:\n</i>"
    if ss is None or len(ss) == 0:
        m += "<i>(None)</i>\n"
    else:
        for k in ss.items():
            m += "%s=%s\n" % k

    ss = user_settings.get(nm)
    m += "<i>Permanent settings:\n</i>"
    if ss is None or len(ss) == 0:
        m += "<i>(None)</i>\n"
    else:
        for k in ss.items():
            m += "%s=%s\n" % k

    await context.bot.send_message(chat_id=bot.message.chat_id, text=m, parse_mode=ParseMode.HTML)


# @send_action(ChatAction.TYPING)
async def u_settings(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not xis_user_ok(bot, context):
        return

    nm = "%s %s" % (bot.message.from_user.first_name, bot.message.from_user.last_name)
    settings = user_session_settings.get(nm, dict())
    args = [s1 for s1 in bot.message.text.split() if len(s1) > 0]
    for i in args:
        j = i.split("=")
        if len(j) == 2:
            settings[j[0]] = j[1]
            print("User setting ", j[0], j[1])

    user_session_settings[nm] = settings


# @send_action(ChatAction.TYPING)
async def pics_dir(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not xis_user_ok(bot, context):
        return
    ndx = 0
    args = [s1 for s1 in bot.message.text.split() if len(s1) > 0]

    if len(args) > 1:
        ndx = int(args[1]) - 1
    else:
        await context.bot.send_message(
            chat_id=bot.message.chat_id,
            text="<i>(.. Please specify at least one picture number.)</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    ndx1 = min(ndx + 20, len(pic_files))

    txt = ""
    i = ndx
    for pf in pic_files[ndx:ndx1]:
        d = pic_dir.get(pf, "")
        i += 1

        txt += "[pic %03d] %s" % (i, pf)

        if len(d) > 0:
            txt += " " + d
        if not os.path.exists(pic_path + pf):
            txt += " MISSING"

        if not txt.endswith("\n"):
            txt += "\n"

    if len(txt) == 0:
        await context.bot.send_message(
            chat_id=bot.message.chat_id, text="<i>(.. No pictures found.)</i>", parse_mode=ParseMode.HTML
        )
    else:

        tx1 = "<i>(.. pictures %d..%d of %d )</i>\n" % (ndx + 1, ndx1, len(pic_files))
        await context.bot.send_message(chat_id=bot.message.chat_id, text=tx1 + txt, parse_mode=ParseMode.HTML)


async def just_message(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    txt = bot.message.text
    if txt is not None:

        if txt.startswith("#"):
            args = [s1 for s1 in txt.split() if len(s1) > 0]

            if len(args) == 1:
                await find_tag(bot, context)
                return

        if txt.lower().startswith("find "):
            await find_substring(bot, context)
            return
        elif txt.lower().startswith("pic "):
            await get_pic(bot, context)
            return
        elif txt.lower().startswith("docs"):
            await all_docs(bot, context)
            return
        elif txt.lower().startswith("pics"):
            await pics_dir(bot, context)
            return
        elif txt.lower().startswith("tags"):
            await tags_dir(bot, context)
            return
        elif txt.lower().startswith("tag "):
            await find_tag(bot, context)
            return
        elif txt.lower().startswith("del "):
            await del_message(bot, context)
            return

    if not xis_admin_ok(bot, context):
        return

    if txt is not None:
        print(txt)
        new_messages.append(txt)
        update_messages()  ## debug
        save_messages()  ## debug
        await context.bot.send_message(
            chat_id=bot.message.chat_id,
            text="<i>(.. message saved as [%03d].)</i>" % len(messages),
            parse_mode=ParseMode.HTML,
        )

        return

    ph = bot.message.photo
    if ph is not None and len(ph) > 0:
        txt = bot.message.caption

        file_id = ph[-1]["file_id"]
        if file_id is None:
            print(bot.message)
            return

        new_file = await context.bot.get_file(file_id)

        tst = time.localtime()
        file_name = pic_path + "%d-%02d-%02d_%02d%02d%02d" % (
            tst.tm_year,
            tst.tm_mon,
            tst.tm_mday,
            tst.tm_hour,
            tst.tm_min,
            tst.tm_sec,
        )
        if os.path.exists(file_name + ".jpg"):
            ii = 0
            while True:
                f1 = file_name + "(%d)" % ii
                if not os.path.exists(f1 + ".jpg"):
                    file_name = f1
                    break
                ii += 1

        await new_file.download_to_drive(file_name + ".jpg")

        if txt is not None:
            m = "/p#i#c %s.jpg %s" % (os.path.basename(file_name), txt)
            pic_dir[os.path.basename(file_name) + ".jpg"] = txt
            new_messages.append(m)
            update_messages()  ## debug
            save_messages()  ## debug
            await context.bot.send_message(
                chat_id=bot.message.chat_id,
                text="<i>(.. message saved as [%03d].)</i>" % len(messages),
                parse_mode=ParseMode.HTML,
            )

        pic_files.append(os.path.basename(file_name) + ".jpg")
    else:
        doc = bot.message.document
        if doc is not None:
            file_name = doc.file_name
            if file_name is not None:
                file_id = doc.file_id

                print("File ", file_id, file_name)
                new_file = context.bot.get_file(file_id)

                nm = "%s %s" % (bot.message.from_user.first_name, bot.message.from_user.last_name)
                upath = user_session_settings[nm].get("uploads", user_settings[nm].get("uploads", ""))
                if not upath.endswith("/"):
                    upath += "/"

                file_name1 = doc_path + upath + file_name
                if not os.path.exists(doc_path + upath):
                    os.mkdir(doc_path + upath)
                new_file.download(file_name1)
                print("Saving file", file_name1)

                m = "/d#o#c %s" % upath + file_name
                new_messages.append(m)
                update_messages()  ## debug
                save_messages()  ## debug
                await context.bot.send_message(
                    chat_id=bot.message.chat_id,
                    text="<i>(.. message saved as [%03d].)</i>" % len(messages),
                    parse_mode=ParseMode.HTML,
                )


# @send_action(ChatAction.TYPING)
async def tech_help(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not xis_user_ok(bot, context):
        return

    cmd_list = []

    for k, i in updater.handlers.items():
        for j in i:
            try:
                for z in j.command:
                    cmd_list.append(z)
            except:
                pass

    t = "<i>Available commands:\n</i>"
    for c in cmd_list:
        t += "%s\n" % c

    await context.bot.send_message(chat_id=bot.message.chat_id, text=t, parse_mode=ParseMode.HTML)


# @send_action(ChatAction.TYPING)
async def show_help(bot: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not xis_user_ok(bot, context):
        return
    t = open(messages_path + "help.txt").read()
    await context.bot.send_message(chat_id=bot.message.chat_id, text=t)


if __name__ == "__main__":

    for a in sys.argv[1:]:
        messages_path = a

    print("Bot Folder: ", messages_path)

    pic_path = messages_path + "images/"
    doc_path = messages_path + "documents/"

    secret = open(messages_path + "secret.txt").read()
    secret = secret.replace("\n", "")

    updater = Application.builder().token(secret).build()
    # updater = Updater(secret)

    if not os.path.exists(messages_path):
        os.mkdir(messages_path)
    if not os.path.exists(pic_path):
        os.mkdir(pic_path)
    if not os.path.exists(doc_path):
        os.mkdir(doc_path)

    m_name = messages_path + "notes.txt"
    if os.path.exists(m_name):
        shutil.copyfile(m_name, m_name + ".saved")

    read_messages()
    cfg = read_config(messages_path + "config.json")
    read_users()
    build_pic_dir()

    updater.add_handler(CommandHandler("hello", hello))
    updater.add_handler(CommandHandler("start", hello))
    updater.add_handler(CommandHandler("find", find_substring))
    updater.add_handler(CommandHandler("f", find_substring))

    updater.add_handler(CommandHandler("re", refresh))
    updater.add_handler(CommandHandler("refresh", refresh))

    updater.add_handler(CommandHandler("d", del_message))
    updater.add_handler(CommandHandler("del", del_message))

    updater.add_handler(CommandHandler("set", u_settings))
    updater.add_handler(CommandHandler("restore", del_u_settings))
    updater.add_handler(CommandHandler("settings", show_settings))

    updater.add_handler(CommandHandler("docs", all_docs))
    updater.add_handler(CommandHandler("pics", pics_dir))
    updater.add_handler(CommandHandler("pic", get_pic))
    updater.add_handler(CommandHandler("delpic", del_pic))

    updater.add_handler(CommandHandler("tags", tags_dir))

    updater.add_handler(CommandHandler("tag", find_tag))

    updater.add_handler(CommandHandler("help", show_help))
    # updater.add_handler(CommandHandler("?", tech_help))

    unknown_handler = MessageHandler(filters.COMMAND, unknown_cmd)
    updater.add_handler(unknown_handler)

    just_handler = MessageHandler(filters.ALL, just_message)
    updater.add_handler(just_handler)

    updater.run_polling()

