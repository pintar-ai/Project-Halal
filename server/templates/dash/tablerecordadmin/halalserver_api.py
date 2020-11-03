#!/usr/bin/env python
from flask import Flask, jsonify, abort, request, make_response, url_for, render_template, redirect, flash
from gevent.pywsgi import WSGIServer
from datetime import datetime, timedelta
import signal
import sys
import os
import string
import configparser
import random 
import string
import json
import requests
import math
import re
import sys
import numpy as np
#from pyproj import Proj, transform
#import logging


app = Flask(__name__, static_url_path='/static')

#log = logging.getLogger('werkzeug')
#log.setLevel(logging.ERROR)

config = configparser.ConfigParser()
config.read('/media/ibrahim/Data/halal-server/config.ini')
app.secret_key = config['GENERAL']['SECRET_KEY']

import sqlite3

# if database isn't exist, then create one with random filename
import uuid
if not config['GENERAL']['SQLITE_PATH'] or not os.path.exists(config['GENERAL']['SQLITE_PATH']):
    
    uuid = str(uuid.uuid4()).split('-')[0]
    config['GENERAL']['SQLITE_PATH'] = "db_{}.sqlite".format(uuid)

    # write new sqlite filename inside our config
    with open('config.ini', 'w') as configfile:
        config.write(configfile)

conn = sqlite3.connect(config['GENERAL']['SQLITE_PATH'], check_same_thread=False)
conn.execute("PRAGMA foreign_keys = 1")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()


from flask_httpauth import HTTPBasicAuth
auth = HTTPBasicAuth()

import flask_login
login_manager = flask_login.LoginManager()
login_manager.init_app(app)

class User(flask_login.UserMixin):
    pass

def remove_dirty_form(dirtylist,number=False):
    dirtylist=dirtylist.replace(']', '')
    dirtylist=dirtylist.replace('[', '')

    splitlist = dirtylist.split (',')
    for index,value in enumerate(splitlist):
        if len(value)<=0:
            continue
        value=value.strip()
        if value[0]=='u':
            value=value[1:]
        value=value.replace("'", "")
        if number:
            value=re.sub("[A-Za-z]","",value)
        splitlist[index]=value
    return splitlist    

@login_manager.user_loader
def user_loader(username):
    lock.acquire(True)
    cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
    lock.release()

    entry = cursor.fetchone()

    if entry is None:
        return
    else :
        user = User()
        user.id = username
        return user

@login_manager.request_loader
def request_loader(request):
    username = request.form.get('username')
    print(username)
    cursor.execute('SELECT * FROM user_table WHERE username=? ', (username,))
    entry = cursor.fetchone()

    if entry is None:
        return
    elif request.form['password'] != entry['password']:
        redirect(url_for('login'))
    else :
        user = User()
        user.id = username
        user.is_authenticated = request.form['password'] == entry['password']

        return user

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'GET':
        return render_template('dash/login_page.html')

    username = request.form['username']

    randomid = id_generator()
    cursor.execute("""UPDATE user_table SET status_log=? WHERE username=?""",(randomid,username))
    conn.commit()

    cursor.execute('SELECT * FROM user_table WHERE username=? ', (username,))
    entry = cursor.fetchone()

    if entry :
        if request.form['password'] == entry['password']:
            user = User()
            user.id = randomid
            flask_login.login_user(user)
            if entry['privilage']==7:
                flash('You were successfully logged in', 'rightadmin')
                return redirect(url_for('show_admin'))
            flash('You were successfully logged in as user', 'rightuser')
            return redirect(url_for('show_user'))
        else:
            error = 'Wrong Username or Password. Try again!'
    
    return render_template('dash/login_page.html', error=error,)


#Render template for template

@app.route('/regtemplate')
def regtemplate():
    None
    return render_template('dash/register.html')

# END OF render template for template

def id_generator(size=10, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

@app.route('/register', methods=['POST'])
def register():
    if not request.json or not 'username' or not 'password' in request.json:
        abort(400)

    username = request.json['username']
    password = request.json['password']
    cursor.execute('SELECT * FROM user_table WHERE username=? ', (username,))
    entry = cursor.fetchone()

    if entry :
        if password == entry['password']:
            randomid=id_generator()
            cursor.execute("""UPDATE user_table SET randomid = ? WHERE username= ? """,(randomid,username))
            conn.commit()
            return jsonify({'randomid': randomid}), 200
        else :
            abort(400, " wrong password")
    else :
        abort(400, " username was not registered")

@app.route('/validate', methods=['POST'])
def validate():
    if not request.json or not 'randomid' in request.json:
        abort(400)

    randomid = request.json['randomid']
    cursor.execute('SELECT * FROM user_table WHERE randomid=? ', (randomid,))
    entry = cursor.fetchone()

    if entry :
        return jsonify({'registered': 'true'}), 200
    else :
        abort(400, " username was not registered")

@app.route('/protected')
@flask_login.login_required
def protected():
    return 'Logged in as: ' + flask_login.current_user.id

@app.route('/logout')
def logout():
    flask_login.logout_user()
    return redirect(url_for('login'))

@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for('login'))
    #return 'Unauthorized'

@auth.get_password
def get_password(username):
    cursor.execute('SELECT * FROM user_table WHERE username=? ', (username,))
    entry = cursor.fetchone()

    if entry is None:
        return None
    else :
        return entry['password']

@auth.error_handler
def unauthorized():
    return make_response(jsonify({'error': 'Unauthorized access'}), 403)

def init_db():
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_table
    (username   TEXT    PRIMARY KEY,
    password    TEXT    NOT NULL,
    fullname    TEXT    NOT NULL,
    email       TEXT    NOT NULL,
    address     TEXT    NOT NULL,
    privilage   INT     NOT NULL,
    randomid    TEXT,
    enabled     BOOLEAN NOT NULL,
    status_log     TEXT,
    date_created    TIMESTAMP   NOT NULL)''')      

    #insert root account to add, edit and remove user. 
    cursor.execute('SELECT * FROM user_table WHERE username=? ', ('root',))
    entry = cursor.fetchone()

    if entry is None:
        cursor.execute('INSERT INTO user_table (username,password,fullname,email,address,privilage,enabled,date_created) VALUES (?,?,?,?,?,?,?,?)', ('root', 'root', 'root', 'root@root', 'root', '7', True, datetime.today().strftime('%Y-%m-%d')))

    cursor.execute('''CREATE TABLE IF NOT EXISTS data_table
    (id             INTEGER         PRIMARY KEY  AUTOINCREMENT,
    itemid          TEXT            NOT NULL,
    itemname        TEXT            NOT NULL,
    mscode          TEXT            NOT NULL,
    date_taken      TIMESTAMP       NOT NULL,
    FOREIGN KEY (mscode) REFERENCES ms_table (mscode))''')
    conn.commit()

    cursor.execute('''CREATE TABLE IF NOT EXISTS ms_table
    (mscode              TEXT            NOT NULL         PRIMARY KEY,
    description         TEXT            NOT NULL)''')
    conn.commit()

    cursor.execute('''CREATE TABLE IF NOT EXISTS record_table
    (id                 INTEGER         PRIMARY KEY  AUTOINCREMENT,
    itemid              TEXT            NOT NULL,
    itemname            TEXT            NOT NULL,
    mscode              TEXT            NOT NULL,
    description         TEXT            NOT NULL)''')
    conn.commit()

user_request = {}

@app.route('/')
def index():
    if flask_login.current_user.is_authenticated:
        username = flask_login.current_user.id
        cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
        entry = cursor.fetchone()

        if entry :
            if entry['privilage']==7:
                return render_template('dash/adminboard.html')
            flask_login.logout_user()
            return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))


@app.route('/admin')
@flask_login.login_required
def show_admin():
    if flask_login.current_user.is_authenticated:
        username = flask_login.current_user.id
        print ("show_admin = {}".format(username))
        cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
        entry = cursor.fetchone()

        username=entry['username']

        if entry :
            if entry['privilage']==7:
                return render_template('dash/adminboard.html', username=username)
            flask_login.logout_user()
            return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))

@app.route('/user')
@flask_login.login_required
def show_user():
    username=flask_login.current_user.id
    print(username)
    cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
    userentry = cursor.fetchone()

    username=userentry['username']

    cursor.execute('SELECT * FROM data_table WHERE username=? ', (username,))
    entry = cursor.fetchall()

    if entry is None:
        flask_login.logout_user()
        return redirect(url_for('login'))
    elif not entry:
        flask_login.logout_user()
        return render_template('empty_map.html')
    else :
        print("got it")
        return redirect(url_for('userdash'))


@app.route('/userdash')
@flask_login.login_required
def userdash():
    if flask_login.current_user.is_authenticated:
        username = flask_login.current_user.id
        cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
        entry = cursor.fetchone()

        cursor.execute('SELECT * FROM user_table WHERE privilage = 7 ')
        lenadmin = cursor.fetchall()

        cursor.execute('SELECT * FROM user_table WHERE privilage = 0 ')
        lenuser = cursor.fetchall()

        

        if entry :
            if entry['privilage']==0:
                return render_template('dash/dashboard.html', lenadmin=lenadmin, lenuser=lenuser) #user dashboard
            flask_login.logout_user()
            return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))

@app.route('/update_admin')
@flask_login.login_required
def update_admin():
    if flask_login.current_user.is_authenticated:
        username = flask_login.current_user.id
        cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
        entry = cursor.fetchone()

        if entry :
            if entry['privilage']==7:
                cursor.execute('SELECT * FROM user_table')
                entry = cursor.fetchall()
                return render_template('dash/table.html', users=entry)
            flask_login.logout_user()
            return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))

@app.route('/userlist')
@flask_login.login_required
def show_userlist():

    if flask_login.current_user.is_authenticated:
        username = flask_login.current_user.id
        cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
        entry= cursor.fetchone()

        username=entry['username']

        if entry :
            if entry['privilage']==7:
                cursor.execute('SELECT * FROM user_table')
                entry = cursor.fetchall()
                return render_template('dash/table.html', users=entry, username=username)
            flask_login.logout_user()
            return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))

@app.route('/itemlist')
@flask_login.login_required
def show_itemlist():

    if flask_login.current_user.is_authenticated:
        username = flask_login.current_user.id
        cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
        entry= cursor.fetchone()

        username=entry['username']

        if entry :
            if entry['privilage']==7:
                cursor.execute('SELECT * FROM data_table')
                entry = cursor.fetchall()
                return render_template('dash/tableitem.html', users=entry, username=username)
            flask_login.logout_user()
            return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))

@app.route('/userprofile')
@flask_login.login_required
def show_userprofile():


    if flask_login.current_user.is_authenticated:
        username = flask_login.current_user.id
        cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
        entry = cursor.fetchone()

        password=entry['password']
        username=entry['username']
        privilage=entry['privilage']
        fname=entry['fullname']
        email=entry['email']
        address=entry['address']
        date_created=entry['date_created']

        if privilage == 7:
            privilagelabel = "Admin"
        else:
            privilagelabel = "User"

        if entry :
            if entry['privilage']==7:
                cursor.execute('SELECT * FROM user_table')
                entry = cursor.fetchall()
                return render_template('dash/user.html', users=entry, username=username, password=password, privilagel=privilagelabel, privilage=privilage, fullname=fname, email=email, address=address, date_created=date_created)
                #flask_login.logout_user()     
            else :
                cursor.execute('SELECT * FROM user_table')
                entry = cursor.fetchall()
                return render_template('dash/userprof.html', users=entry, username=username, password=password, privilagel=privilagelabel, privilage=privilage, fullname=fname, email=email, address=address, date_created=date_created)
            flask_login.logout_user()
    else:
        return redirect(url_for('login'))


@app.route('/recordList')
@flask_login.login_required
def show_recordList():
    if flask_login.current_user.is_authenticated:
        username = flask_login.current_user.id
        cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
        entry = cursor.fetchone()

        username=entry['username']

        if entry :
            if entry['privilage']==7:
                data = getRecordDataAdmin()
                return render_template('dash/tablerecordadmin.html', users=data, username=username)
                #flask_login.logout_user()
            
            else :
                data = getRecordDataUser(username)
                return render_template('dash/tablerecorduser.html', users=data,username=username)
            flask_login.logout_user()
    else:
        return redirect(url_for('login'))


@app.route('/reg', methods=['POST'])
def reg():
    username    = request.form.get('username')
    password    = request.form.get('password')
    fullname    = request.form.get('fullname')
    email       = request.form.get('email')
    address     = request.form.get('address')
    #print(username)
    cursor.execute('SELECT * FROM user_table WHERE username=? ', (username,))
    entry = cursor.fetchone()
    #print(entry)

    if entry is None:
        cursor.execute('INSERT INTO user_table (username,password,fullname,email,address,privilage,enabled,date_created) VALUES (?,?,?,?,?,?,?,?)', (username, password, fullname, email, address,0, True, datetime.today().strftime('%Y-%m-%d')))
        conn.commit()
        flash('Welcome {}! You can login now.'.format(username), 'successreg')
        return redirect(url_for('login'))
        
    else:
        flash('Invalid username / Duplicate', 'wrongreg')
        return redirect(url_for('login'))   


#User Profile Editing
@app.route('/adduser', methods=['POST'])
@flask_login.login_required
def create_user():
    if flask_login.current_user.is_authenticated:
        username = flask_login.current_user.id

        print ("create_user : {}".format(username))

        cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
        entry = cursor.fetchone()
        

        if entry :
            if entry['privilage']==7:              
                username    = request.form.get('username')
                password    = request.form.get('password')
                privilage   = request.form.get('privilage')
                fullname    = request.form.get('fullname')
                address     = request.form.get('address')
                email       = request.form.get('email')

                if not username or not password or not privilage or not fullname or not address or not email:
                    abort(400)

                cursor.execute('SELECT * FROM user_table WHERE username=?', (username,))
                entry = cursor.fetchone()

                if entry is None:
                    try:
                        cursor.execute('INSERT INTO user_table (username,password,fullname,address,email,privilage,enabled,date_created) VALUES (?,?,?,?,?,?,?,?)', (username, password, fullname, address, email, privilage, True, datetime.today().strftime('%Y-%m-%d')))
                        conn.commit()
                        cursor.execute('SELECT * FROM user_table')
                        entry = cursor.fetchall()
                        flash('You were successfully add new user')
                        return render_template('dash/table.html', users=entry)
                    except Exception as e:
                        print("error")
                else :
                    return jsonify({'status': 'user already recorded'}), 200
                
            flask_login.logout_user()
            return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))

#User Profile Editing
@app.route('/additem', methods=['POST'])
@flask_login.login_required
def create_item():
    if flask_login.current_user.is_authenticated:
        username = flask_login.current_user.id
        cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
        entry = cursor.fetchone()     

        if entry :
            if entry['privilage']==7:                
                itemname    = request.form.get('itemname')
                itemid    = request.form.get('itemid')
                mscode   = request.form.get('mscode')

                if not itemname or not itemid or not mscode:
                    abort(400)

                if mscode == "0":
                    msvalue="MS 1500:2009"
                elif mscode == "1":
                    msvalue="MS 2200 Part 1:2008"
                elif mscode == "2":
                    msvalue="MS 2400-1:2010(P)"
                elif mscode == "3":
                    msvalue="MS 2400-2:2010(P)"
                elif mscode == "4":
                    msvalue="MS 2400-3:2010(P)"

                
                cursor.execute('SELECT * FROM data_table WHERE itemname=? AND itemid=? AND mscode=?', (itemname,itemid,msvalue))
                entry = cursor.fetchone()
                
                if entry is None:
                    try:
                        cursor.execute('INSERT INTO data_table (itemid,itemname,mscode) VALUES (?,?,?)', (itemid, itemname, msvalue))
                        conn.commit()
                        cursor.execute('SELECT * FROM data_table')
                        entry = cursor.fetchall()
                        flash('You were successfully add new item')
                        return render_template('dash/tableitem.html', users=entry)
                    except Exception as e:
                        print("error")
                else :
                    return jsonify({'status': 'item already recorded'}), 200
                
            return redirect(url_for('show_itemlist'))
    else:
        return redirect(url_for('login'))

@app.route('/updateuser', methods=['POST'])
@flask_login.login_required
def updateuser():
    if flask_login.current_user.is_authenticated:
        username = request.form.get('username')
        password = request.form.get('password')
        repassword = request.form.get('repassword')
        privilage = request.form.get('privilage')

        if password == repassword:
            cursor.execute("""UPDATE user_table SET privilage = ?, password = ? WHERE username = ?""", (privilage,password,username))
            flash('You were successfully update user')
            conn.commit()
        else:
            flash('Not saved. Please enter the valid password.')

        

        return redirect(url_for('show_userlist'))

@app.route('/updateitem', methods=['POST'])
@flask_login.login_required
def updateitem():
    if flask_login.current_user.is_authenticated:
        itemname = request.form.get('itemname')
        itemid = request.form.get('itemid')
        mscode = request.form.get('mscode')
        msvalue=""

    print ("updateitem mscode : {}, {}, {}".format(itemid, itemname, mscode))

    if mscode == "0":
        msvalue="MS 1500:2009"
    elif mscode == "1":
        msvalue="MS 2200 Part 1:2008"
    elif mscode == "2":
        msvalue="MS 2400-1:2010(P)"
    elif mscode == "3":
        msvalue="MS 2400-2:2010(P)"
    elif mscode == "4":
        msvalue="MS 2400-3:2010(P)"

    print ("updateitem msvalue : {}".format(msvalue))

    cursor.execute('SELECT * FROM data_table where itemid=? AND itemname=? AND mscode=?', (itemid,itemname,msvalue))
    entry=cursor.fetchone()

    print ("updateitem entry : {}".format(entry))

    if entry :            
        cursor.execute("""UPDATE data_table SET itemid = ?, itemname = ? WHERE mscode = ?""", (itemid,itemname,msvalue))
        flash('You were successfully update user')
        conn.commit()
            
        return redirect(url_for('show_itemlist'))
    else:
        flash('Wrong Input')
        return redirect(url_for('show_itemlist'))

    flash('No Item Exist')
    return redirect(url_for('show_itemlist'))

@app.route('/updateuserprof', methods=['POST'])
@flask_login.login_required
def updateuserprof():
    if flask_login.current_user.is_authenticated:
        username = request.form.get('username')
        password = request.form.get('password')
        repassword = request.form.get('repassword')
        privilage = request.form.get('privilage')

        if password == repassword :
            cursor.execute("""UPDATE user_table SET privilage = ?, password = ? WHERE username = ?""", (privilage,password,username))
            conn.commit()
            flash('You were successfully update password')
        else :
            flash('Password not saved. Try again.')

        print("{} done".format(password))
        print("{} done".format(repassword))
        print("{} done".format(privilage))
        print("{} done".format(username))

        return redirect(url_for('show_userprofile'))

@app.route('/deleteuser', methods=['POST'])
@flask_login.login_required
def deleteuser():

    if flask_login.current_user.is_authenticated:
        username = request.form.get('username')
        
        cursor.execute('SELECT * FROM user_table WHERE username=? ', (username,))
        entry = cursor.fetchone()

        if entry is not None:
            cursor.execute('DELETE from user_table WHERE username = ?', (username,))
            conn.commit()
            
            #cursor.execute('SELECT * FROM data_table WHERE username=? ', (username,))
            #cursor.execute('DELETE from user_table WHERE username = ?', (username,))
            #conn.commit()

        else :
            return redirect(url_for('show_userlist'))

        flash('You were successfully delete user')
            

        #return redirect(url_for('update_admin'))
        return redirect(url_for('show_userlist'))

@app.route('/deleteitem', methods=['POST'])
@flask_login.login_required
def deleteitem():

    if flask_login.current_user.is_authenticated:
        iid = request.form.get('itemid')
        
        cursor.execute('SELECT * FROM data_table WHERE itemid=? ', (iid,))
        entry = cursor.fetchone()

        if entry is not None:
            cursor.execute('DELETE FROM data_table WHERE itemid=? ', (iid,))
            conn.commit()
        else:
            return redirect(url_for('show_itemlist'))
            

        flash('You were successfully delete an item')
            
        return redirect(url_for('show_itemlist'))
    
#End User Profile Editing

#Get Data from server

@app.route('/requestItem',methods=['POST','GET'])
def requestItem():

    print (request.json)

    if not request.json or not 'itemid' or not 'mscode' in request.json:
        abort(400)

    item = request.json['itemid']
    ms=request.json['mscode']
    user="test1"

    time_act = (datetime.now() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    print (time_act)

    cursor.execute(' SELECT * FROM data_table WHERE itemid=? ',(item,))
    entry = cursor.fetchone()

    if entry :

        item_id=entry['itemid']
        item_name=entry['itemname']
        item_mscode=entry['mscode']

        print(item_id,item_name,item_mscode)

        cursor.execute('SELECT * FROM ms_table WHERE mscode=?',(item_mscode,))
        entry= cursor.fetchone()

        item_desc=entry['description']

        cursor.execute('INSERT INTO record_table (itemid,itemname,mscode,description,datetaken,username) VALUES (?,?,?,?,?,?)',(item_id,item_name,item_mscode,item_desc,time_act,user))
        conn.commit()

        return jsonify({'Item Name' : item_name, 'Desc' : item_desc }, 200)
    else:
        abort(400, "Record not found!")

temp_data = {}

@app.route('/gimick',methods=['POST','GET'])
def gimick():

    #request_path = True
    global temp_data
    if not request.json or not 'request' in request.json:
        abort(400)

    item = request.json['request']
    #json.dumps(marker)

    if item == True :
        temp_data = {'data':json.dumps({"item":item}),'sent':False}
        return jsonify({'status' : "received"})
    else:
        abort(400, "Fail!")

@app.route('/gimick2',methods=['POST','GET'])
@flask_login.login_required
def gimick2():

    print ("\ngimick2\n")

    return render_template('dash/gimick-slide.html')


@app.route('/streamadmin')
@flask_login.login_required
def streamadmin():

    #username = flask_login.current_user.id
    global temp_data
    print ("Test user_request : {}".format(temp_data))
    if not temp_data:
        response = app.response_class(
        response="data:no data\n\n",
        status=200,
        mimetype='text/event-stream'
        )
    elif not temp_data['sent']:
        response = app.response_class(
        response="data:%s\n\n"% temp_data['data'],
        status=200,
        mimetype='text/event-stream'
        )
        temp_data['sent']=True
    elif temp_data['sent']:
        response = app.response_class(
        response="data:no data\n\n",
        status=200,
        mimetype='text/event-stream'
        )
    return response


#Function to get data from server for Admin record table
def getRecordDataAdmin():

    try:
        lock.acquire(True)
        cursor.execute('SELECT * FROM record_table ORDER BY datetaken DESC')
        entry = cursor.fetchall()
    finally:
        lock.release()

    return(entry)

#Function to get data from server for User record table
def getRecordDataUser(Uname):

    try:
        username=Uname
        lock.acquire(True)
        cursor.execute('SELECT * FROM record_table WHERE username=? ORDER BY datetaken DESC',(username,))
        entry = cursor.fetchall()
    finally:
        lock.release()

    return(entry)
  
#End Get Data from server
@app.errorhandler(400)
def custom400(error):
    response = jsonify({'message': error.description})
    return response, 400

def kill_server():
        print('You pressed Ctrl+C!')
        http_server.stop()
        sys.exit(0)

##### Data for Chart.js
import threading
lock = threading.Lock()

if __name__ == '__main__':
    init_db()
    
    http_server = app.run(host='0.0.0.0', port=5000, threaded=True)
    #http_server = WSGIServer((config['WEB-SERVER']['HOST'], int(config['WEB-SERVER']['PORT'])), app)
    print("\nRunning on {}:{}...\n".format(config['WEB-SERVER']['HOST'], config['WEB-SERVER']['PORT']))

    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        kill_server()
