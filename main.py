from flask import Flask, request, jsonify
from flask_sslify import SSLify
import requests
from time import sleep
import schedule
import time
import threading
import re
import os
import copy
from InstagramAPI import InstagramAPI
from flask_sqlalchemy import SQLAlchemy
from collections import deque

API = InstagramAPI('##############', '####################')
API.login()
app = Flask(__name__)
sslify = SSLify(app)


SQLALCHEMY_DATABASE_URI = "postgres://#####################################################"
# SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://root:1@localhost/bot14'

app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_POOL_RECYCLE"] = 299
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


URL = 'https://api.telegram.org/bot################################################/'
ADMINS = [289951289, 54891143, 450195887]
KICK_THEM = []
CHAT_ID = -1001129943420
RANGE_OF_TIMES = None
COUNTER = 0
SET_OF_RECEIVERS = set()
RECEIVERS_COUNTER = 0
OLD_PARTICIPANTS = dict()
WARN_THESE_USERS = []

class WarnedUsers(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.Integer, unique=True)
    warns = db.Column(db.Integer, nullable=True)
    username = db.Column(db.String(100), default='')
    name = db.Column(db.String(150), default='')
    surname = db.Column(db.String(150), default='')


class Time(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String(10))

class Hashtags(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180))


def get_likers(media_id):
    sleep(0.1)
    likers = []
    API.getMediaLikers(media_id)
    for c in reversed(API.LastJson['users']):
        likers.append(c)
    API.LastJson.get('username', False)
    result = {x['username'] for x in likers}
    return result

def get_list_of_likers(pks):
    sleep(10)
    list_of_likers = [get_likers(x) for x in pks]
    return list_of_likers


def get_filtered_results(participants, tuple_with_set_and_pks):
    global OLD_PARTICIPANTS
    OLD_PARTICIPANTS = copy.deepcopy(participants)
    inner_rem = []
    external_rem = []
    set_of_receivers, pks = tuple_with_set_and_pks
    for x in participants:
        for k in participants[x].keys():
            if k not in set_of_receivers:
                if len(participants[x]) > 1:
                    inner_rem.append(k)
                else:
                    external_rem.append(x)

    for x in external_rem:
        del participants[x]

    for k in inner_rem:
        for x in participants:
            if k in participants[x]:
                del participants[x][k]

    list_of_pics_likers = get_list_of_likers(pks)
    tolerance_len = round(len(pks) * 0.90)
    # print('get filtered results')

    for kv in participants.items():
        for x in participants[kv[0]]:
            participants[kv[0]][x] = sum([participants[kv[0]][x]
                                        in pics for pics in list_of_pics_likers])

    return participants, tolerance_len, len(pks)


def form_db_and_response(participants, tolerance, receivers_len):
    print(PARTICIPANTS, 'PARTICIPANTS')
    key_value_likes = ''
    warn_this_users = set()
    for x in participants.items():
        for k in x[1]:
            print(participants[x[0]][k], participants[x[0]])
            if participants[x[0]][k] < (tolerance-1):
                warn_this_users.add(x[0])

        for k,v in participants[x[0]].items():
            key_value_likes += f"{k} : {v} likes\n"

    for x in warn_this_users:
        obj = WarnedUsers.query.filter(WarnedUsers.telegram_id==x).first()
        if obj:
            if obj.warns + 1 <= 5:
                obj.warns += 1
                db.session.commit()


        else:
            new_obj = WarnedUsers(telegram_id=x, warns=1,
                                  username=PARTICIPANTS_IDENTIFIERS[x]['username'])
            db.session.add(new_obj)
            db.session.commit()


    send_message(f"Round ended!\nTable with results:\n{key_value_likes}")
    warn_for_incorrect_data = set()

    for x in OLD_PARTICIPANTS.items():
        for k, v in x[1].items():
            print(k,v)
            if k in WARN_THESE_USERS:
                warn_for_incorrect_data.add(x[0])

    for x in warn_for_incorrect_data:
        obj = WarnedUsers.query.filter(WarnedUsers.telegram_id==x).first()
        if obj:
            if obj.warns + 1 <= 5:
                obj.warns += 1
                db.session.commit()

        else:
            new_obj = WarnedUsers(telegram_id=x, warns=1,
                                  username=PARTICIPANTS_IDENTIFIERS[x]['username'])
            db.session.add(new_obj)
            db.session.commit()


    if WARN_THESE_USERS:
        send_message('\n'.join(f"@{PARTICIPANTS_IDENTIFIERS[id_]['username']} | {PARTICIPANTS_IDENTIFIERS[id_]['first_name']} : "
                               f"hai sbagliato a prenotarti, non ti sei prenotato o ti sei prenotato tardi!!!Ti becchi un’ammonizione. "
                                         f"Attualmente {PARTICIPANTS_IDENTIFIERS[id_]['first_name']} "
                      f"hai: {WarnedUsers.query.filter(WarnedUsers.telegram_id==id_).first().warns}/5 AMMONIZIONI"
                               for id_ in warn_for_incorrect_data))

    message = '\n'.join(f"@{PARTICIPANTS_IDENTIFIERS[id_]['username']} | {PARTICIPANTS_IDENTIFIERS[id_]['first_name']} " \
                      f"{PARTICIPANTS_IDENTIFIERS[id_]['last_name']} | Non hai lasciato {', '.join(f'da {k} - liked {v} foto (non hai completato il round con questo profilo)' if v < (tolerance-1) else f'da {k} - liked {v} foto (hai completato il round da  questo profilo)' for k,v in participants[id_].items())} "
                      f"foto su {receivers_len}. Sei stato AMMONITO. Attualmente {PARTICIPANTS_IDENTIFIERS[id_]['first_name']} "
                      f"hai: {WarnedUsers.query.filter(WarnedUsers.telegram_id==id_).first().warns}/5 AMMONIZIONI"
                      for id_ in warn_this_users)

    for x in warn_this_users:
        obj = WarnedUsers.query.filter(WarnedUsers.telegram_id==x).first()
        kickParticipant(obj)

    for x in warn_for_incorrect_data:
        obj = WarnedUsers.query.filter(WarnedUsers.telegram_id==x).first()
        kickParticipant(obj)


    if not message and not WARN_THESE_USERS:
        message = 'Il round è finito! Congratulazioni 🎉 nessun furbetto!!'

    return message


def get_feed_by_hashtag(hashtag):
    global WARN_THESE_USERS
    counter = 0
    pks = []
    maxResults = 500
    nextMaxId = ''
    set_of_receivers = set()
    # print('GET FEED BY HASHTAG')
    while len(pks) < maxResults:

        API.getHashtagFeed(hashtag.name[1:], nextMaxId)
        mediasJson = API.LastJson

        try:
            for c in mediasJson['ranked_items']:
                if c['user']['username'] in SET_OF_RECEIVERS \
                and c['user']['username'] not in set_of_receivers:

                    set_of_receivers.add(c['user']['username'])
                    counter += 1
                    pks.append(c['pk'])
        except KeyError:
            pass

        for c in mediasJson['items']:
            if c['user']['username'] in SET_OF_RECEIVERS\
            and c['user']['username'] not in set_of_receivers:

                set_of_receivers.add(c['user']['username'])
                counter += 1
                pks.append(c['pk'])

        if mediasJson['more_available'] == True:
            nextMaxId = mediasJson['next_max_id']
        else:
            break
    db.session.delete(hashtag)
    db.session.commit()

    send_message('Stop drop! Non puoi più prenotarti')
    send_message("Stop drop. Utenti prenotati {}. Lista degli utenti prenotati e che "
                 "hanno aggiunto hashtag:\n{}".format(counter, '\n'.join(x for x in set_of_receivers)))

    for x in SET_OF_RECEIVERS.difference(set_of_receivers):
        WARN_THESE_USERS.append(x)

    print(WARN_THESE_USERS)
    return set_of_receivers, pks



def send_message(text='something'):
    url = URL + 'sendMessage'
    answer = {'chat_id': CHAT_ID, 'text': text}
    r = requests.post(url, json=answer)
    return r.json()

MAIN_FUC = False
started = False
PARTICIPANTS = dict()
PARTICIPANTS_IDENTIFIERS = dict()

def kickParticipant(obj):
    if obj.warns >= 5:
        data = {'chat_id': CHAT_ID, 'user_id': obj.telegram_id}
        requests.post(URL + 'kickChatMember', data)
        send_message('Ha accumulato 5 ammonizioni ed è stato bannato dal gruppo.')
        db.session.delete(obj)
        db.session.commit()
    pass


def main():
    global SET_OF_RECEIVERS
    global MAIN_FUC
    if MAIN_FUC:
        print('main function')
        global started
        started = True
        hashtag = Hashtags.query.order_by(Hashtags.id).first()

        send_message(f"Il round è iniziato! L’hashtag è {hashtag.name}")
        sleep(900)
        print(requests.get('https://frozen-bayou-13074.herokuapp.com/'))
        send_message('Hurry up, guys! 15 minutes left!')
        sleep(900)
        print(requests.get('https://frozen-bayou-13074.herokuapp.com/'))
        started = False
        tuple_with_set_and_pks = get_feed_by_hashtag(hashtag)
        sleep(700)
        send_message('Corri a lasciare i likes!! Mancano 13 minuti 😱')
        sleep(350)
        print(requests.get('https://frozen-bayou-13074.herokuapp.com/'))
        sleep(450)
        participants, tolerance, receivers_len = get_filtered_results(PARTICIPANTS, tuple_with_set_and_pks)
        sleep(100)
        send_message(form_db_and_response(participants, tolerance, receivers_len))
        PARTICIPANTS.clear()
        SET_OF_RECEIVERS.clear()
        MAIN_FUC = False

@app.before_first_request
def activate_job():
    def get_times(q):
        while True:
            sleep(240)
            print('here, updating db')
            db.session.commit()
            q.append([x for x in Time.query.all()])

    def run_job(q):
        while True:

            global COUNTER
            if COUNTER:
                db.session.commit()
                COUNTER -= 1
            if q:
                print('run job here')
                value = q.pop()
                print([schedule.every(1).day.at(x.time).do(main) for x in value])

            global MAIN_FUC
            MAIN_FUC = True

            schedule.run_pending()
            time.sleep(1)

    q = deque()
    q.append([x for x in Time.query.all()])

    thread = threading.Thread(target=run_job, args=(q,))
    thread1 = threading.Thread(target=get_times, args=(q,))
    thread.start()
    thread1.start()



@app.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        r = request.get_json()
        # print(r)
        if r.get('message') and not r['message']['from']['is_bot'] \
                            and not r['message'].get('new_chat_member')\
                            and not r['message'].get('left_chat_member')\
                            and not r['message'].get('photo')\
                            and not r['message'].get('document')\
                            and not r['message'].get('voice')\
                            and not r['message'].get('sticker')\
                            and not r['message'].get('video')\
                            and not r['message'].get('pinned_message'):
            # chat_id = r['message']['chat']['id']
            message = r['message']['text']
            from_ = r['message']['from']
            from_id = from_['id']

            if started:
                l = [re.findall('@[a-zA-Z0-9._]+', x) for x in message.lower().split('\n')]
                global RECEIVERS_COUNTER
                global SET_OF_RECEIVERS
                if l:
                    print('LIST WITH recv and providers')
                    print(l)
                    for x in l:
                        if not x and '/leave' not in message:
                            data = {'chat_id': CHAT_ID, 'message_id': r['message']['message_id']}
                            requests.post(URL + 'deleteMessage', data)

                        elif '/leave' in message and from_id in PARTICIPANTS:
                            for x in PARTICIPANTS[from_id]:
                                SET_OF_RECEIVERS.remove(x)

                            del PARTICIPANTS[from_id]
                            send_message(f"{from_.get('first_name', '“Utente”')} ha abbandonato il round")
                            RECEIVERS_COUNTER -= 1

                        else:
                            recv_and_providers = [[x[0][1:], x[1][1:]] if len(x) > 1 else [x[0][1:], x[0][1:]] for x in l if x]

                            for i,x in enumerate(l):
                                if x:
                                    SET_OF_RECEIVERS.add(x[0][1:])
                                    RECEIVERS_COUNTER += 1

                    r_p = f"{from_.get('first_name', 'Participant')} your accounts:\n" + '\n'.join(f"{i}. Ricevi su: {x[0]}\n{i}. Lascia con: {x[1]}"
                                                for i,x in enumerate(recv_and_providers, 1))
                    send_message(r_p)

                    PARTICIPANTS[from_id] = dict(recv_and_providers)
                    PARTICIPANTS_IDENTIFIERS[from_id] = {'first_name': from_.get('first_name', 'name not specified'),
                                                         'last_name': from_.get('last_name', 'surname not specified'),
                                                         'username': from_.get('username', 'username not specified')
                                                         }


            if r['message']['from']['id'] in ADMINS and '/time' in message:
                s = ' '.join(x.time for x in Time.query.all())
                send_message(f'Il round inizia alle: {s}')

            if r['message']['from']['id'] in ADMINS and '/change_time' in message:
                for x in Time.query.all():
                    db.session.delete(x)
                global RANGE_OF_TIMES
                global COUNTER
                RANGE_OF_TIMES = re.findall('\d\d:\d\d', message)
                for x in RANGE_OF_TIMES:
                    new_time = Time(time=x)
                    db.session.add(new_time)
                    db.session.commit()
                    COUNTER += 1

                result = Time.query.all()

                if RANGE_OF_TIMES: send_message(f"Current time ranges are: {', '.join(x.time for x in result)}")
                else: send_message('Enter a VALID TIME.\nFollow the pattern:\n/change_time '
                                   '19:21, 10:01, 23:34 (or more times for more rounds)\nPattern would be 2 numbers colon 2 numbers')

            if from_id in ADMINS and '/remove_group_warns' in message:

                if '/remove_group_warns yes, confirm this action.' in message:
                    for x in WarnedUsers.query.all():
                        db.session.delete(x)
                    db.session.commit()
                    send_message('Le ammonizioni sono state rimosse.')
                else:
                    send_message('Please, confirm your actions.\nIn order to remove an entire table with warns '
                                 'confirm your intentions. Make a full copy of this:\n'
                                 '/remove_group_warns yes, confirm this action.')


            if '/check_my_warns' in message:
                result = WarnedUsers.query.filter(WarnedUsers.telegram_id==from_id).first()
                if result: send_message(f'Attualmente hai {result.warns} ammonizioni')
                else: send_message("Congratulazioni! Non sei un furbetto!! Non hai ammonizioni")



            if from_id in ADMINS and '/assign_hashtags' in message:
                hashtags = re.findall('#\w+', message)
                current_hashtags = ', '.join(x.name for x in Hashtags.query.all())

                text = f'Current list of hashtags: {current_hashtags}\nIn order to reset ' \
                       f'and set new list of hashtags, please follow this pattern.\n' \
                                 '\n/assign_hashtags #mailegood, #something, #this_is_hashtag31321'
                admin_id = r['message']['chat'].get('id')
                url = URL + 'sendMessage'

                if hashtags:
                    Hashtags.query.delete()
                    for h in hashtags:
                        hashtag = Hashtags(name=h)
                        db.session.add(hashtag)
                    db.session.commit()
                    new_hashtags = ', '.join(x.name for x in Hashtags.query.all())
                    text = f'Current list of new hashtags: {new_hashtags}'
                    answer = {'chat_id': admin_id, 'text': text}
                    requests.post(url, json=answer)
                else:
                    answer = {'chat_id': admin_id, 'text': text}
                    requests.post(url, json=answer)



            if from_id in ADMINS and '/warn' in message:
                l = [x for x in message.split(' ') if x]
                if len(r['message'].get('entities'))>1:
                    d = r['message'].get('entities')[1]
                    if d:
                        if len(l) == 2 and l[1][0] == '@' and d['type']=='mention':
                            res = WarnedUsers.query.filter(WarnedUsers.username==l[1][1:]).first()
                            if res:
                                res.warns += 1
                                send_message(f'Current numbers of warns of {l[1][1:]}: {res.warns}')
                                db.session.commit()
                                kickParticipant(res)
                            else:
                                send_message("This telegram user not in database because he's still didn't took part"
                                             "at rounds")
                        elif len(l) == 2 and d.get('user'):
                            res = WarnedUsers.query.filter(WarnedUsers.telegram_id == d.get('user')['id']).first()

                            if res:
                                res.warns += 1
                                send_message(f"Current numbers of warns of {d['user'].get('first_name','Name not specified')}: {res.warns}")
                                db.session.commit()
                                kickParticipant(res)
                            else:
                                send_message("You made a mistake in pattern or in USER name OR "
                                             "this telegram user not in database because he's still didn't took part"
                                             "at rounds")

                else:
                    send_message('Enter the telegram username (preferable) with the help of telegram hint\n'
                             'Follow this pattern:\n/warn @RobSelv\nOR\n/warn @choose_a_user_without_username')

            if from_id in ADMINS and '/remove_warn' in message:
                l = [x for x in message.split(' ') if x]
                if len(r['message'].get('entities')) > 1:
                    d = r['message'].get('entities')[1]
                    if d:
                        if len(l) == 2 and l[1][0] == '@' and d['type'] == 'mention':
                            res = WarnedUsers.query.filter(WarnedUsers.username == l[1][1:]).first()
                            if res:
                                if res.warns:
                                    res.warns -= 1
                                    db.session.commit()
                                send_message(f'Current numbers of warns of {l[1][1:]}: {res.warns}')
                                db.session.commit()
                            else:
                                send_message("This telegram user not in database because he's still didn't took part"
                                             "at rounds")
                        elif len(l) == 2 and d.get('user'):
                            res = WarnedUsers.query.filter(WarnedUsers.telegram_id == d.get('user')['id']).first()
                            if res:
                                if res.warns:
                                    res.warns -= 1
                                    db.session.commit()
                                send_message(
                                    f"Current numbers of warns of {d['user'].get('first_name','Name not specified')}: {res.warns}")

                            else:
                                send_message("You made a mistake in pattern or in USER name OR "
                                             "this telegram user not in database because he's still didn't took part"
                                             "at rounds")

                else:
                    send_message('Enter the telegram username (preferable) with the help of telegram hint\n'
                                 'Follow this pattern:\n/remove_warn @RobSelv\nOR\n/remove_warn @choose_a_user_without_username')

            if '/current_time' in message:
                send_message(f"current web-server time: {__import__('datetime').datetime.now()}")

            if from_id in ADMINS and message == '/help':
                send_message('Lista dei comandi disponibili:\n/help\n/time\n'
                                      '/change_time\n/remove_group_warns\n/warn\n/remove_warn\n/assign_hashtags\n/check_my_warns\n/leave')
            elif message == '/help':
                send_message('Lista dei comandi disponibili:\n/help\n/check_my_warns\n/leave')



        elif r.get('message') and r['message'].get('new_chat_participant'):
            name = r['message']['new_chat_participant'].get('first_name', 'newcomer')
            greetings = f"Ciao {name}!\nBenvenuto nel gruppo dedicato allo scambio Like per  pagine Food di Instagram" \
                        f" 😬\nSiamo il primo gruppo nato e nonché più forte presente su Instagram, gli altri sono solo" \
                        f" spazzatura 🤣🤣\n\nSCOPO:L’obiettivo è quello di postare una foto ad un orario determinato e" \
                        f" scambiarci i like tra tutti gli iscritti.Questi Like, ricevuti nei primi minuti dalla" \
                        f" pubblicazione da pagine della tua stessa nicchia (e non pagine di collanine e orecchini)," \
                        f" aumenteranno le possibilità di far diventare virale la foto e di conseguenza incrementare la" \
                        f" tua popolarità ricevendo tanti Like e nuovi followers!!\n\nFUNZIONAMENTOPer poter ricevere i" \
                        f" like, devi “prenotarti” nel “round” ed inserire nella tua foto l’hashtag personalizzato del" \
                        f" gruppo (cambia ad ogni round)Facciamo due round al giorno, alle 14 e alle 21Come funziona?\n\n1)" \
                        f" Se hai foto da pubblicare,scrivi il tuo username in questo modo @tuousernameinstagram quando" \
                        f" verrà invitato il messaggio di inizio round (tra le 13:31 e le 13:59 e tra le ore 20:31 e" \
                        f" 20:59)\n2) se non hai foto da pubblicare è gradito lasciare comunque i Like agli altri del" \
                        f" gruppo.\n3) la foto deve essere pubblicata TASSATIVAMENTE entro le 14:00 e le 21:00\n4) alle ore" \
                        f" 14:00 e alle ore 21:00 cerca su Instagram l’hashtag e metti like a tutte le foto che vedi" \
                        f" nella colonna RECENTI ENTRO E NON OLTRE LE 14:15 e le 21:15 !!!\n\n✅ È consigliato mettere" \
                        f" l’hashtag a foto appena pubblicate, metterlo a foto vecchie non darà risultati! I Risultati" \
                        f" si hanno solo ricevendo tanti Like nei primi minuti dalla pubblicazione!\n✅ Un solo profilo" \
                        f" per un solo account Telegram\n✅ Non scrivere nel gruppo round\n✅ Una sola foto per hashtag" \
                        f"\n✅ Se non rispetti gli orari o non lasci i like  ricevi un’ammonizione\n✅ Dopo 5 ammonizioni" \
                        f" BAN\n✅ Se non ti piacciono le regole esci ora prima che ti cacci io 🤣\nSe hai domande scrivi " \
                        f"a @robselv\nPer il servizio crescita (aumento like e followers) contatta @robselv\n"
            send_message(f"{greetings}\n"
                         f"Lista dei comandi disponibili:\n"
                         f"/help\n/check_my_warns\n/leave")

        return jsonify(r)
    return '<h1>Bot welcomes you!</h1>'

# new bot https://api.telegram.org/bot#########################/setWebhook?url=https://frozen-bayou-13074.herokuapp.com/
# https://api.telegram.org/bot#######################/setWebhook?url=https://51df41cf.ngrok.io
# ALTER DATABASE dbname CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    # app.run()