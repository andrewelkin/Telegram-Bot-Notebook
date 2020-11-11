import os, sys, shutil
from telegram.ext import Updater, CommandHandler, Filters, MessageHandler
from telegram import ParseMode, ChatAction
import unicodedata
from functools import wraps

import time
import codecs
import re
import string

messages_path = "./"

"""
 File "secret.txt" contains a single line with secret code (access token) you received from the telegram bot father
 File "users.txt" has this format for each line:
 
 
 <First> <Last>[,admin=1][,uploads=<subdir for personal uploads"]
 
 John Doe,uploads=JD_uploads/
 Jane Doe,admin=1
 
 only admins can delete messages and upload new ones. all plain users just search/view messages
 
"""

messages = []
new_messages = []
admins = set()
users = set()
picdir = {}
pic_files = []
all_tags = {}

max_messages_in_search = 10

user_settings = {}
user_session_settings = {}


def read_users():
    global users, admins
    name = messages_path + "users.txt"
    if not os.path.exists(name):
        return users
    users = set()
    admins = set()
    f = open(name)
    for s in f:
        s = s.replace("\n", "")
        items = s.split(",")
        users.add(items[0])

        settings = {}
        for i in items[1:]:
            j = i.split("=")
            if len(j) == 2:
                if j[0] == "admin":
                    if j[1] == "1":
                        admins.add(items[0])
                        print("added admin '%s'" % items[0])
                else:
                    settings[j[0]] = j[1]

        user_settings[items[0]] = settings

        print("added user '%s'" % items[0], settings.items())
        user_session_settings[items[0]] = {}

    print("%d users known for the bot" % len(users))


def is_user_ok(first, last):
    return "%s %s" % (first, last) in users


def is_admin_ok(first, last):
    return "%s %s" % (first, last) in admins


def xis_user_ok(bot, update):
    if not is_user_ok(update.message.from_user.first_name, update.message.from_user.last_name):
        bot.send_message(
            chat_id=update.message.chat_id,
            text="<i>(.. You are not authorized to use this service.)</i>",
            parse_mode=ParseMode.HTML,
        )
        print(update.message.from_user.first_name, update.message.from_user.last_name, "not authorized for the service")
        return False

    return True


def xis_admin_ok(bot, update):
    if not is_admin_ok(update.message.from_user.first_name, update.message.from_user.last_name):
        bot.send_message(
            chat_id=update.message.chat_id,
            text="<i>(.. You are not authorized for this operation.)</i>",
            parse_mode=ParseMode.HTML,
        )
        print(update.message.from_user.first_name, update.message.from_user.last_name, "not authorized for the op")
        return False

    return True


def build_pic_dir():
    global picdir, pic_files

    pic_files = []
    picdir = {}
    for m in messages:
        if m.startswith("/p#i#c"):
            m = m[7:]
            fname = m.split(" ")[0]
            m = m[len(fname) + 1:]
            picdir[fname] = m

    pic_files = [s for s in os.listdir(pic_path) if s.lower().endswith(".jpg")]


def update_tags(m):
    # wordList = re.sub("[^#a-zA-Z0-9_]", " ", curr_message).split()
    sp = string.punctuation.replace("#", "")
    wordList = re.sub("[" + sp + "]", "", m).split()
    for w in wordList:
        if w.startswith("#") and len(w) > 1:
            l = all_tags.setdefault(w, set())
            l.add(len(messages) - 1)


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
    msgname = messages_path + "notes.txt"
    if not os.path.exists(msgname):
        return []
    # f = file(msgname)
    f = codecs.open(msgname, "r", "cp1251")
    alls = f.read()

    messages = []
    curr_message = ""
    for s in alls.split("\n"):
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


def save_messages1():
    msgname = messages_path + "notes.txt"
    f = open(msgname, "w")
    for s in messages:
        f.write("---\n")
        f.write(s)
        if not s.endswith("\n"):
            f.write("\n")
    f.close()


def save_messages():
    msgname = messages_path + "notes.txt"
    # f = file(msgname,'w')
    f = codecs.open(msgname, "w", "cp1251")
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
            update = args[0]
            bot = args[1].bot
            a = args[1].args

            bot.send_chat_action(chat_id=update.message.chat_id, action=action)
            func(bot, update, a)

        return command_func

    return decorator



def hello(bot, update):
    update.message.reply_text(
        "Hello {}".format(update.message.from_user.first_name)
        + ", I have %d notes" % (len(messages) + len(new_messages))
    )

    delusettings(bot, update, [])


def send_message(bot, update, mess_no, full=False):
    if len(messages) < mess_no:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="<i>(..could not find message %03d)</i> " % (mess_no),
            parse_mode=ParseMode.HTML,
        )

    m1 = messages[mess_no - 1]
    if m1.startswith("/d#o#c"):
        m1 = m1[7:]

        if m1.startswith('"'):
            fname = m1[1:].split('"')[0].replace("\n", "")
        else:
            fname = m1.split(" ")[0].replace("\n", "")

        if full:
            try:
                fo = open(doc_path + fname, "rb")
                bot.send_document(chat_id=update.message.chat_id, document=fo)
                fo.close()
            except:
                bot.send_message(
                    chat_id=update.message.chat_id,
                    text="[%03d] <i>(..document is missing %s)</i> " % (mess_no, fname),
                    parse_mode=ParseMode.HTML,
                )
        else:
            bot.send_message(chat_id=update.message.chat_id, text="[%03d] (%s) %s" % (mess_no, "document", fname))

    elif m1.startswith("/p#i#c"):
        m1 = m1[7:]
        fname = m1.split(" ")[0].replace("\n", "")
        m1 = m1[len(fname) + 1:]

        if full:

            try:
                fo = open(pic_path + fname, "rb")
                bot.send_photo(chat_id=update.message.chat_id, photo=fo, caption="[%03d] " % (mess_no) + m1)
                fo.close()
            except:
                bot.send_message(
                    chat_id=update.message.chat_id,
                    text="[%03d] <i>(..picture is missing %s)</i> " % (mess_no, m1),
                    parse_mode=ParseMode.HTML,
                )

        else:

            bot.send_message(chat_id=update.message.chat_id, text="[%03d] (%s)" % (mess_no, "picture") + m1)

    else:
        bot.send_message(chat_id=update.message.chat_id, text="[%03d] " % (mess_no) + m1)


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


def all_docs(bot, update, args):
    res = scan4docs(doc_path)
    s = set()
    for m in messages:
        if m.startswith("/d#o#c"):
            m = m[7:]
            if m.startswith('"'):
                fname = m[1:].split('"')[0]
            else:
                fname = m.split(" ")[0]

            s.add(fname.replace("\n", ""))

    for r in res:
        if not r in s:
            if r.find(" ") >= 0:
                m = '/d#o#c "%s"' % r
            else:
                m = "/d#o#c %s" % r

            new_messages.append(m)

    update_messages()  ## debug
    save_messages()  ## debug

    if len(args) == 0:
        find_substring(bot, update, ["d#o#c"])
    else:
        find_substring(bot, update, ["+d#o#c"] + args)


@send_action(ChatAction.TYPING)
def find_substring(bot, update, args):
    if not xis_user_ok(bot, update):
        return
    included = []
    excluded = []
    mustbe = []
    anything = False

    if len(args) == 0:
        update.message.reply_text(
            "Please use syntax:  /f [+<must_be_sub_string1> ..] [!<must_not_be_sub_string1> ..] [<substring1> ..]  "
        )
        return

    done = 0
    for s in args:

        s = s.replace("'", "")
        s = s.replace('"', "")

        # s = unicodedata.normalize('NFKD', s).encode('cp1251', 'ignore')

        if s.startswith("!"):
            excluded.append(s[1:].lower())
        elif s.startswith("+"):
            mustbe.append(s[1:].lower())
        else:
            included.append(s.lower())

    mess_no = 0
    for m1 in messages:
        mess_no += 1
        m = m1.lower()
        needbreak = False
        for e in excluded:
            if m.find(e) >= 0:
                needbreak = True
                break
        if needbreak:
            continue
        for o in mustbe:
            if m.find(o) < 0:
                needbreak = True
                break
        if needbreak:
            continue

        maybe = False  ##if len(mustbe)==0 else True
        if not maybe:
            for o in included:
                if m.find(o) >= 0:
                    maybe = True
                    break
        if maybe:
            done += 1
            if done >= max_messages_in_search:
                bot.send_message(
                    chat_id=update.message.chat_id,
                    text="<i>(.. there are more notes in search, please rectify.)</i>",
                    parse_mode=ParseMode.HTML,
                )
                break

            anything = True
            send_message(bot, update, mess_no)

    if not anything:
        bot.send_message(
            chat_id=update.message.chat_id, text="<i>(.. there are no matches.)</i>", parse_mode=ParseMode.HTML
        )


def refresh(bot, update):
    print("Refreshing..")
    global messages, new_messages
    read_messages()
    new_messages = []
    read_users()
    build_pic_dir()


## exit()


def del_message(bot, update, args):
    if not xis_admin_ok(bot, update):
        return

    if len(args) < 1:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="<i>(.. Please specify at least one message number.)</i>",
            parse_mode=ParseMode.HTML,
        )

        return

    todel = set()
    for a in args:
        i = int(a) - 1
        if i >= len(messages):
            continue
        print("Deleting message no %d" % i)

        m = messages[i]
        if m.startswith("/d#o#c"):
            m = m[7:]
            if m.startswith('"'):
                fname = m[1:].split('"')[0].replace("\n", "")
            else:
                fname = m.split(" ")[0].replace("\n", "")

            try:
                os.unlink(doc_path + fname)
                print("Deleted file ", doc_path + fname)
            except:

                print("Could not delete ", doc_path + fname)

        todel.add(i)

    todel = list(todel)
    todel.sort()
    todel.reverse()

    repl = ""
    for td in todel:
        repl += "<i>(..message #%d deleted)</i>\n" % (td + 1)
        del messages[td]

    if repl != "":
        bot.send_message(chat_id=update.message.chat_id, text=repl, parse_mode=ParseMode.HTML)

    save_messages()  ## debug
    rebuild_tags()
    build_pic_dir()


def unknown_cmd(bot, update):
    txt = update.message["text"]
    if txt is not None and len(txt) > 1:
        txt = txt[1:]
        if txt[0] == "#":
            txt = txt[1:]
            return find_tag(bot, update, [txt])

        if txt.isdigit():
            num = int(txt)
            send_message(bot, update, num, True)
            return

    bot.send_message(chat_id=update.message.chat_id, text="Sorry, I didn't understand that command:  " + txt)


def get_pic(bot, update, args):
    if not xis_user_ok(bot, update):
        return
    ndx = 0
    if len(args) > 0:
        ndx = int(args[0]) - 1

    if ndx >= len(pic_files):
        bot.send_message(
            chat_id=update.message.chat_id,
            text="<i>(.. Photo #%d not found.)</i>" % (ndx + 1),
            parse_mode=ParseMode.HTML,
        )
        return

    fname = pic_files[ndx]
    capt = picdir.get(fname, fname)
    capt = "[pic %03d] " % (ndx + 1) + capt

    try:
        fo = open(pic_path + fname, "rb")
        bot.send_photo(chat_id=update.message.chat_id, photo=fo, caption=capt)
    except:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="<i>(..picture #%d is missing)</i> " % (ndx + 1),
            parse_mode=ParseMode.HTML,
        )


def del_pic(bot, update, args):
    if not xis_admin_ok(bot, update):
        return
    if len(args) < 1:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="<i>(.. Please specify at least one picture number.)</i>",
            parse_mode=ParseMode.HTML,
        )

        return

    ndx = int(args[0]) - 1
    if ndx >= len(pic_files):
        bot.send_message(
            chat_id=update.message.chat_id,
            text="<i>(.. Photo #%d not found.)</i>" % (ndx + 1),
            parse_mode=ParseMode.HTML,
        )
        return

    if pic_files[ndx] == "(..deleted)":
        bot.send_message(
            chat_id=update.message.chat_id,
            text="<i>(..picture #%d is already deleted)</i> " % (ndx + 1),
            parse_mode=ParseMode.HTML,
        )
        return

    fname = pic_files[ndx]

    try:
        os.unlink(pic_path + fname)
        bot.send_message(
            chat_id=update.message.chat_id,
            text="<i>(..picture #%d deleted)</i> " % (ndx + 1),
            parse_mode=ParseMode.HTML,
        )
        pic_files[ndx] = "(..deleted)"
    except:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="<i>(..picture #%d is missing)</i> " % (ndx + 1),
            parse_mode=ParseMode.HTML,
        )


@send_action(ChatAction.TYPING)
def find_tag(bot, update, args):
    if not xis_user_ok(bot, update):
        return
    if len(args) < 1:
        bot.send_message(
            chat_id=update.message.chat_id, text="<i>(.. Please specify tag.)</i>", parse_mode=ParseMode.HTML
        )
        return

    t = args[0]
    if not t.startswith("#"):
        t = "#" + t
    l = all_tags[t]
    if l is None:
        bot.send_message(chat_id=update.message.chat_id, text="<i>(..tag is not found)</i> ", parse_mode=ParseMode.HTML)
        return

    l = list(l)
    l.sort()
    for ndx in l[:10]:
        send_message(bot, update, ndx + 1, len(l) == 1)


def tags_dir(bot, update, args):
    if not xis_user_ok(bot, update):
        return

    rep = "<i>(.. tags found: %d)</i>\n" % len(all_tags)

    for k, l in all_tags.items():
        rep += "%s (%d)," % (k, len(l))

    if len(rep) > 0:
        rep = rep[: len(rep) - 1]
    bot.send_message(chat_id=update.message.chat_id, text=rep, parse_mode=ParseMode.HTML)


def delusettings(bot, update, args):
    if not xis_user_ok(bot, update):
        return
    nm = "%s %s" % (update.message.from_user.first_name, update.message.from_user.last_name)
    user_session_settings[nm] = {}
    bot.send_message(
        chat_id=update.message.chat_id,
        text="<i>(.. session level user settings deleted.)</i>",
        parse_mode=ParseMode.HTML,
    )


def showsettings(bot, update, args):
    if not xis_user_ok(bot, update):
        return

    nm = "%s %s" % (update.message.from_user.first_name, update.message.from_user.last_name)
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

    bot.send_message(chat_id=update.message.chat_id, text=m, parse_mode=ParseMode.HTML)


def usettings(bot, update, args):
    if not xis_user_ok(bot, update):
        return

    nm = "%s %s" % (update.message.from_user.first_name, update.message.from_user.last_name)
    settings = user_session_settings.get(nm, dict())
    for i in args:
        j = i.split("=")
        if len(j) == 2:
            settings[j[0]] = j[1]
            print("User setting ", j[0], j[1])

    user_session_settings[nm] = settings


def pics_dir(bot, update, args):
    if not xis_user_ok(bot, update):
        return
    ndx = 0
    if len(args) > 0:
        ndx = int(args[0]) - 1

    ndx1 = min(ndx + 20, len(pic_files))

    txt = ""
    i = ndx
    for pf in pic_files[ndx:ndx1]:
        d = picdir.get(pf, "")
        i += 1

        txt += "[pic %03d] %s" % (i, pf)

        if len(d) > 0:
            txt += " " + d
        if not os.path.exists(pic_path + pf):
            txt += " MISSING"

        if not txt.endswith("\n"):
            txt += "\n"

    if len(txt) == 0:
        bot.send_message(
            chat_id=update.message.chat_id, text="<i>(.. No pictures found.)</i>", parse_mode=ParseMode.HTML
        )
    else:

        tx1 = "<i>(.. pictures %d..%d of %d )</i>\n" % (ndx + 1, ndx1, len(pic_files))
        bot.send_message(chat_id=update.message.chat_id, text=tx1 + txt, parse_mode=ParseMode.HTML)


##@send_action(ChatAction.TYPING)
def just_message(bot, update):
    txt = update.message["text"]
    if txt is not None:
        if txt.startswith("#"):
            args = txt.split(" ")
            if len(args) == 1:
                return find_tag(bot, update, args)

        if txt.lower().startswith("find "):
            return find_substring(bot, update, txt[5:].split(" "))
        if txt.lower().startswith("pic "):
            return get_pic(bot, update, [s for s in txt[4:].split(" ") if len(s) > 0])
        if txt.lower().startswith("docs"):
            return all_docs(bot, update, [s for s in txt[4:].split(" ") if len(s) > 0])
        if txt.lower().startswith("pics"):
            return pics_dir(bot, update, [s for s in txt[4:].split(" ") if len(s) > 0])
        if txt.lower().startswith("tags"):
            return tags_dir(bot, update, txt[5:].split(" "))
        if txt.lower().startswith("tag "):
            return find_tag(bot, update, txt[4:].split(" "))
        if txt.lower().startswith("del "):
            return del_message(bot, update, [s for s in txt[4:].split(" ") if len(s) > 0])

    if not xis_admin_ok(bot, update):
        return

    if txt is not None:
        print(txt)
        new_messages.append(txt)
        update_messages()  ## debug
        save_messages()  ## debug
        bot.send_message(
            chat_id=update.message.chat_id,
            text="<i>(.. message saved as [%03d].)</i>" % len(messages),
            parse_mode=ParseMode.HTML,
        )

        return

    ph = update.message["photo"]
    if ph is not None and len(ph) > 0:
        txt = update.message["caption"]

        file_id = ph[-1]["file_id"]
        if file_id is None:
            print(update.message)
            return

        newFile = bot.get_file(file_id)

        tst = time.localtime()
        fname = pic_path + "%d-%02d-%02d_%02d%02d%02d" % (
            tst.tm_year,
            tst.tm_mon,
            tst.tm_mday,
            tst.tm_hour,
            tst.tm_min,
            tst.tm_sec,
        )
        if os.path.exists(fname + ".jpg"):
            ii = 0
            while True:
                f1 = fname + "(%d)" % ii
                if not os.path.exists(f1 + ".jpg"):
                    fname = f1
                    break
                ii += 1

        newFile.download(fname + ".jpg")

        if txt is not None:
            m = "/p#i#c %s.jpg %s" % (os.path.basename(fname), txt)
            picdir[os.path.basename(fname) + ".jpg"] = txt
            new_messages.append(m)
            update_messages()  ## debug
            save_messages()  ## debug
            bot.send_message(
                chat_id=update.message.chat_id,
                text="<i>(.. message saved as [%03d].)</i>" % len(messages),
                parse_mode=ParseMode.HTML,
            )

        pic_files.append(os.path.basename(fname) + ".jpg")
    else:
        doc = update.message["document"]
        if doc is not None:
            fname = doc["file_name"]
            if fname is not None:
                file_id = doc["file_id"]

                print("File ", file_id, fname)
                newFile = bot.get_file(file_id)

                nm = "%s %s" % (update.message.from_user.first_name, update.message.from_user.last_name)
                upath = user_session_settings[nm].get("uploads", user_settings[nm].get("uploads", ""))
                if not upath.endswith("/"):
                    upath += "/"

                fname1 = doc_path + upath + fname
                if not os.path.exists(doc_path + upath):
                    os.mkdir(doc_path + upath)
                newFile.download(fname1)
                print("Saving file", fname1)

                m = "/d#o#c %s" % upath + fname
                new_messages.append(m)
                update_messages()  ## debug
                save_messages()  ## debug
                bot.send_message(
                    chat_id=update.message.chat_id,
                    text="<i>(.. message saved as [%03d].)</i>" % len(messages),
                    parse_mode=ParseMode.HTML,
                )


def techhelp(bot, update, args):
    if not xis_user_ok(bot, update):
        return

    cmdlist = []

    for k, i in updater.dispatcher.handlers.items():
        for j in i:
            try:
                for z in j.command:
                    cmdlist.append(z)
            except:
                pass

    t = "<i>Available commands:\n</i>"
    for c in cmdlist:
        t += "%s\n" % c

    bot.send_message(chat_id=update.message.chat_id, text=t, parse_mode=ParseMode.HTML)


def showhelp(bot, update, args):
    if not xis_user_ok(bot, update):
        return
    t = open(messages_path + "help.txt").read()
    bot.send_message(chat_id=update.message.chat_id, text=t)


if __name__ == "__main__":

    for a in sys.argv[1:]:
        messages_path = a

    print("Bot Folder: ", messages_path)

    pic_path = messages_path + "images/"
    doc_path = messages_path + "documents/"

    secret = open(messages_path + "secret.txt").read()
    secret = secret.replace("\n", "")

    updater = Updater(secret)

    if not os.path.exists(messages_path):
        os.mkdir(messages_path)
    if not os.path.exists(pic_path):
        os.mkdir(pic_path)
    if not os.path.exists(doc_path):
        os.mkdir(doc_path)

    msgname = messages_path + "notes.txt"
    if os.path.exists(msgname):
        # os.unlink(msgname+".saved")
        shutil.copy(msgname, msgname + ".saved")

    read_messages()
    read_users()
    build_pic_dir()

    updater.dispatcher.add_handler(CommandHandler("hello", hello))
    updater.dispatcher.add_handler(CommandHandler("start", hello))
    updater.dispatcher.add_handler(CommandHandler("find", find_substring, pass_args=True))
    # updater.dispatcher.add_handler(CommandHandler('term', stop))
    updater.dispatcher.add_handler(CommandHandler("f", find_substring, pass_args=True))

    updater.dispatcher.add_handler(CommandHandler("re", refresh))
    updater.dispatcher.add_handler(CommandHandler("refresh", refresh))

    updater.dispatcher.add_handler(CommandHandler("d", del_message, pass_args=True))
    updater.dispatcher.add_handler(CommandHandler("del", del_message, pass_args=True))

    updater.dispatcher.add_handler(CommandHandler("set", usettings, pass_args=True))
    updater.dispatcher.add_handler(CommandHandler("restore", delusettings, pass_args=True))
    updater.dispatcher.add_handler(CommandHandler("settings", showsettings, pass_args=True))

    updater.dispatcher.add_handler(CommandHandler("docs", all_docs, pass_args=True))
    updater.dispatcher.add_handler(CommandHandler("pics", pics_dir, pass_args=True))
    updater.dispatcher.add_handler(CommandHandler("pic", get_pic, pass_args=True))
    updater.dispatcher.add_handler(CommandHandler("delpic", del_pic, pass_args=True))

    updater.dispatcher.add_handler(CommandHandler("tags", tags_dir, pass_args=True))

    updater.dispatcher.add_handler(CommandHandler("tag", find_tag, pass_args=True))

    updater.dispatcher.add_handler(CommandHandler("help", showhelp, pass_args=True))
    # updater.dispatcher.add_handler(CommandHandler("?", techhelp, pass_args=True))

    unknown_handler = MessageHandler(Filters.command, unknown_cmd)
    updater.dispatcher.add_handler(unknown_handler)

    just_handler = MessageHandler(Filters.all, just_message)
    updater.dispatcher.add_handler(just_handler)

    updater.start_polling()
    updater.idle()

"""
{'delete_chat_photo': False, '
_effective_attachment': {'file_name': u'LimeTradingApiOverview.pdf', 'file_id': 'BQADBAADuAcAAm4mEVDR2ypIOOlDaAI', 'mime_type': u'application/pdf', 'file_size': 414315}, 'new_chat_photo': [], 'from': {'first_name': u'Andy', 'last_name': u'Elkin', 'is_bot': False, 'id': 250300756, 'language_code': u'en'}, 'photo': [], 'channel_chat_created': False, 'caption_entities': [], 'entities': [], 'new_chat_members': [], 'supergroup_chat_created': False, 'chat': {'first_name': u'Andy', 'last_name': u'Elkin', 'type': u'private', 'id': 25030}, 'date': 1543662249, 'group_chat_created': False,
 'document': {'file_name': u'LimeTradingApiOverview.pdf', 'file_id': 'BQADBAADuAcAAm4mEVDR2ypIOOlDaAI', 'mime_type': u'application/pdf', 'file_size': 414315}, 'message_id': 1409}




{'delete_chat_photo': False, 'new_chat_photo': [], 'caption': u'jjj', 'from': {'first_name': u'Andy', 'last_name': u'Elkin', 'is_bot': False, 'id': 250300756, 'language_code': u'en'}, 
'photo': [{'width': 90, 'file_size': 1314, 'file_id': 'AgADBAADurExG24mEVDTg87ylyDdablHoBoABLO-HBJl-CrnnEwFAAEC', 'height': 78}, {'width': 320, 'file_size': 17104, 'file_id': 'AgADBAADurExG24mEVDTg87ylyDdablHoBoABFLzbppvaDDgnUwFAAEC', 'height': 278}, {'width': 669, 'file_size': 44810, 'file_id': 'AgADBAADurExG24mEVDTg87ylyDdablHoBoABLZEFfOPFdrmnkwFAAEC', 'height': 582}], 'channel_chat_created': False, 'caption_entities': [], 'entities': [], 'new_chat_members': [], 'supergroup_chat_created': False, 'chat': {'first_name': u'Andy', 'last_name': u'Elkin', 'type': u'private', 'id': 25030}, 'date': 1543663348, 'group_chat_created': False, 'message_id': 1411}

"""
