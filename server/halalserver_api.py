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
config.read('/media/ibrahim/Data/halal_server/config.ini')
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
        return render_template('dash/login_page.html',)
        #return render_template('login.html', error=error,)

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
    #return render_template('login.html', error=error,)

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
    datetaken      TIMESTAMP       NOT NULL,
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

def fetchall_data(query,param=None):
    try:
        lock.acquire(True)
        if param:
            cursor.execute(query, param)
        else:
            cursor.execute(query)
        entry = cursor.fetchall()
    finally:
        lock.release()
        return entry

#######################################################################################################################################################
########################################################           MAP MANAGEMENT          ############################################################
#######################################################################################################################################################

'''
    cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
    userentry = cursor.fetchone()

    username=userentry['username']

    cursor.execute('SELECT * FROM record_table WHERE username=? ', (username,))
    entry = cursor.fetchall()
'''

user_request = {}

def create_marker(date=None,username=None,bbox=None):
    marker={}
    entry={}
    i=0
    if username and date:
        entry=fetchall_data('SELECT * FROM record_table WHERE username=? AND datetaken LIKE ?', (username,date+"%",))
    elif username and bbox:
        entry=fetchall_data('SELECT * FROM record_table WHERE latitude>? AND latitude<? AND longitude>? AND longitude<? AND username=?', (bbox['min1'], bbox['min2'], bbox['max1'], bbox['max2'],username,))
    elif date:
        entry=fetchall_data('SELECT * FROM record_table WHERE datetaken LIKE ?', (date+"%",))
    elif bbox:
        entry=fetchall_data('SELECT * FROM record_table WHERE latitude>? AND latitude<? AND longitude>? AND longitude<?', (bbox['min1'], bbox['min2'], bbox['max1'], bbox['max2'],))
    elif username=="all":
        entry=fetchall_data('SELECT * FROM record_table')
    elif username:
        print ("masuk2")
        print (username)
        entry=fetchall_data('SELECT * FROM record_table WHERE username=?', (username,))

    if entry:
        for row in entry:
            latitude = row['latitude']
            longitude = row['longitude']
            datetaken = row['datetaken']
            user = row['username']
            itemid = row['itemid']
            itemname = row['itemname']
            mscode = row['mscode']
            desc = row['description']

            description2 = ('<br><b>Taken by</b>: '+str(user)+
                            '<br><b>Item ID</b>: '+str(itemid)+
                            '<br><b>Item Name</b>: '+str(itemname)+
                            '<br><b>MS Code</b>: '+str(mscode)+
                            '<br><b>Description</b>: '+str(desc)+
                            '<br><b>Latitude</b>: '+str(latitude)+
                            '<br><b>Longitude</b>: '+str(longitude)+
                            '<br><b>Date Taken</b>: '+str(datetaken)+

                            '<form accept-charset="UTF-8" action="/showinv" method="post" target="_blank" style="text-align: center; margin:3px;">'+
                            '<div class="form-group">'+
                            '<input type="hidden" value="'+str(datetaken)+'" name="date">'+
                            '</div>')

            objectstreetlight = 'object'+str(i)
            marker.update({objectstreetlight:{'lat':latitude, 'lng':longitude,'description':description2}})
            i+=1
    return marker


@app.route('/pushadmin', methods=['GET'])
@flask_login.login_required
def pushadmin():
    if flask_login.current_user.is_authenticated:
        date = request.args.get('date')
        date = str(date)
        username = flask_login.current_user.id
        global user_request
    else:
        return redirect(url_for('login'))

    cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
    userentry = cursor.fetchone()

    username=userentry['username']

    if userentry :
        if userentry['privilage']==7:
            if date:
                streetlight_timebased = create_marker(date=date)
                user_request[username]={'data':json.dumps(streetlight_timebased),'sent':False}
                return ('', 204)
            else:
                return ('', 204)
        elif userentry['privilage']==0:
            if date:
                streetlight_timebased = create_marker(date=date)
                user_request[username]={'data':json.dumps(streetlight_timebased),'sent':False}
                return ('', 204)
            else:
                return ('', 204)
        else:
            return redirect(url_for('login'))

@app.route('/streamadminmap')
@flask_login.login_required
def streamadminmap():
    if flask_login.current_user.is_authenticated:
        username = flask_login.current_user.id
        cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
        userentry = cursor.fetchone()

        username=userentry['username']

        global user_request
        if not username in user_request:
            response = app.response_class(
            response="data:no data\n\n",
            status=200,
            mimetype='text/event-stream'
            )
        elif not user_request[username]['sent']:
            response = app.response_class(
            response="data:%s\n\n"% user_request[username]['data'],
            status=200,
            mimetype='text/event-stream'
            )
            user_request[username]['sent']=True
        elif user_request[username]['sent']:
            response = app.response_class(
            response="data:no data\n\n",
            status=200,
            mimetype='text/event-stream'
            )
        return response
    else:
        return redirect(url_for('login'))

@app.route('/push', methods=['GET'])
@flask_login.login_required
def push():
    if flask_login.current_user.is_authenticated:
        date = request.args.get('date')
        date = str(date)
        username = flask_login.current_user.id
        global user_request
    else:
        return redirect(url_for('login'))

    cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
    userentry = cursor.fetchone()

    username=userentry['username']

    if userentry :
        if userentry['privilage']==0:
            if date:
                streetlight_timebased = create_marker(date=date,username=username)
                user_request[username]={'data':json.dumps(streetlight_timebased),'sent':False}
                return ('', 204)
            else:
                return ('', 204)
        else:
            return redirect(url_for('login'))
    

@app.route('/stream')
@flask_login.login_required
def stream():
    if flask_login.current_user.is_authenticated:
        username = flask_login.current_user.id

        cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
        userentry = cursor.fetchone()

        username=userentry['username']
        
        global user_request
        if not username in user_request:
            response = app.response_class(
            response="data:no data\n\n",
            status=200,
            mimetype='text/event-stream'
            )
        elif not user_request[username]['sent']:
            response = app.response_class(
            response="data:%s\n\n"% user_request[username]['data'],
            status=200,
            mimetype='text/event-stream'
            )
            user_request[username]['sent']=True
        elif user_request[username]['sent']:
            response = app.response_class(
            response="data:no data\n\n",
            status=200,
            mimetype='text/event-stream'
            )
        return response
    else:
        return redirect(url_for('login'))

def findCenterLonLat (geolocations): # ( (12,23),(23,23),(43,45) )
    x,y,z =0,0,0
    #print(geolocations)

    for lat, lon in (geolocations):
        #print('\n\n')
        #print(lat)
        #print(lon)
        #print('\n\n')
        lat = math.radians(float(lat))
        lon = math.radians(float(lon))
        x += math.cos(lat) * math.cos(lon)
        y += math.cos(lat) * math.sin(lon)
        z += math.sin(lat)

    x = float(x / len(geolocations))
    y = float(y / len(geolocations))
    z = float(z / len(geolocations)) 
    
    center_lon = (math.atan2(y, x))
    center_lat = math.atan2(z, math.sqrt(x * x + y * y))

    return (math.degrees(center_lat), math.degrees(center_lon))
    
global min1, min2, max1, max2, dname
min1,min2,max1,max2=0,0,0,0
dname = "View All State"

@app.route('/mapbox_proxy', methods=['GET'])
@flask_login.login_required
def mapbox_proxy():
    #this route provide proxy to prevent client side known the API token for generate Mapbox tile to our map. We want to keep it secret right?
    if flask_login.current_user.is_authenticated:
        filename = str(request.args.get('location'))+".png"
        url = "https://api.tiles.mapbox.com/v4/mapbox.satellite/"+filename

        querystring = {"access_token":"pk.eyJ1IjoicGVyY2VwdHJvbnNlcnZpY2VzIiwiYSI6ImNqdnEyZWM4NDJmZWo0OXFvNnZmMDgwODcifQ.XbWZ8kPvVjiOF8QgyoQeuA"}

        payload = ""
        headers = {
            'cache-control': "no-cache",
            'Postman-Token': "40ebb8bc-d6fd-49b0-9d61-9608ca8ae1a3"
            }
        filename=filename.replace("/", "")
        response = requests.request("GET", url, data=payload, headers=headers, params=querystring)
        reply = make_response(response.content)
        reply.headers.set('Content-Type', 'image/png')
        reply.headers.set(
            'Content-Disposition', 'attachment', filename=filename)
        return reply
    else:
        return redirect(url_for('login'))

@app.route('/adminmap')
@flask_login.login_required
def adminmap():
    if not flask_login.current_user.is_authenticated:
        return redirect(url_for('login'))
    username=flask_login.current_user.id
    marker={}

    cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
    userentry = cursor.fetchone()

    username=userentry['username']

    streetlight_areabased = None
    streetlight_timebased = None
    listdate = []
    listusername = []

    #Query marker Area Based
    min1 = request.args.get("min1") #minlat
    min2 = request.args.get("min2") #minlon
    max1 = request.args.get("max1") #maxlat
    max2 = request.args.get("max2") #maxlon
    dname = request.args.get("dname")

    if (min1 is None):
        min1, min2, max1, max2 = 0,0,0,0
    else :
        min1, min2, max1, max2 = min1, min2, max1, max2
        
        bbox = {"min1":min1, "min2":min2, "max1":max1, "max2":max2}
        streetlight_areabased = create_marker(bbox=bbox)

    if streetlight_areabased:
        object_names = set()
        for key in streetlight_areabased:
            object_names.add(key)
            latlon_list=[(streetlight_areabased[key]['lat'],streetlight_areabased[key]['lng'])]

        flash('Focus on {} with {} streetlight'.format(dname, len(object_names)))
        error = str("Focus on {} with {} streetlight".format(dname,len(object_names)))
        center_lat,center_lon = findCenterLonLat(latlon_list)

    #Query marker Time Based
    try:
        lock.acquire(True)
        cursor.execute('SELECT datetaken,username FROM record_table')
        entry = cursor.fetchall()
    finally:
        lock.release()
    for i in entry:
        datetaken = i['datetaken']
        user = i['username']
        date_only = str(datetime.strptime(datetaken,'%Y-%m-%d %H:%M:%S').date())
        if not date_only in listdate:
            listdate.append(date_only)
        if not user in listusername:
            listusername.append(user)
    if listdate:
        max_date = max(listdate)
        streetlight_timebased = create_marker(date=max_date)

    if streetlight_timebased:
        for key in streetlight_timebased:
            latlon_list=[(streetlight_timebased[key]['lat'],streetlight_timebased[key]['lng'])]
        center_lat,center_lon = findCenterLonLat(latlon_list)

    #Choose the area based if any
    if min1==0:
        streetlight=streetlight_timebased
    else :
        streetlight=streetlight_areabased
        
    return render_template('/dash/admin-maps3.html', clat = center_lat, clon = center_lon, telco=streetlight, dname=dname, min1=min1, min2=min2, max1=max1, max2=max2, data=json.dumps(listdate), marker=marker, username=username, user=listusername)



@app.route('/usermap')
@flask_login.login_required
def usermap():
    if not flask_login.current_user.is_authenticated:
        return redirect(url_for('login'))
    username=flask_login.current_user.id
    marker={} 

    cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
    userentry = cursor.fetchone()

    username=userentry['username']

    #Query marker Area Based
    min1 = request.args.get("min1") #minlat
    min2 = request.args.get("min2") #minlon
    max1 = request.args.get("max1") #maxlat
    max2 = request.args.get("max2") #maxlon
    dname = request.args.get("dname")

    streetlight_areabased = None
    streetlight_timebased = None

    center_lat = 0.0
    center_lon = 0.0

    if (min1 is None):
        min1, min2, max1, max2 = 0,0,0,0
    else :
        min1, min2, max1, max2 = min1, min2, max1, max2
        
        bbox = {"min1":min1, "min2":min2, "max1":max1, "max2":max2}
        streetlight_areabased = create_marker(username=username,bbox=bbox)

    if streetlight_areabased:
        object_names = set()
        for key in streetlight_areabased:
            object_names.add(key)
            latlon_list=[(streetlight_areabased[key]['lat'],streetlight_areabased[key]['lng'])]

        flash('Focus on {} with {} streetlight'.format(dname, len(object_names)))
        error = str("Focus on {} with {} streetlight".format(dname,len(object_names)))
        center_lat,center_lon = findCenterLonLat(latlon_list)

    #Query marker Time Based
    listdate = []
    for i in fetchall_data('SELECT datetaken FROM record_table WHERE username=? ', (username,)):
        datetaken = i['datetaken']
        date_only = str(datetime.strptime(datetaken,'%Y-%m-%d %H:%M:%S').date())
        if not date_only in listdate:
            listdate.append(date_only)
    if listdate:
        max_date = max(listdate)
        streetlight_timebased = create_marker(username=username,date=max_date)

    if streetlight_timebased:
        for key in streetlight_timebased:
            latlon_list=[(streetlight_timebased[key]['lat'],streetlight_timebased[key]['lng'])]
        center_lat,center_lon = findCenterLonLat(latlon_list)

    #Choose the area based if any
    if min1==0:
        streetlight=streetlight_timebased
    else :
        streetlight=streetlight_areabased
    return render_template('/dash/user-map3.html',telco=streetlight, clat = center_lat, clon = center_lon, dname=dname,min1=min1, min2=min2, max1=max1, max2=max2, marker=marker, username=username, data=json.dumps(listdate))

@app.route('/searchloc',methods=['POST'])
@flask_login.login_required
def searchloc():
    if not flask_login.current_user.is_authenticated:
        return redirect(url_for('login'))
    username=flask_login.current_user.id

    cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (username,))
    userentry = cursor.fetchone()

    username=userentry['username']
    
    if flask_login.current_user.is_authenticated:
        loc = request.form.get('state')
    print (loc)
    if loc=="Choose State":
        return ('', 204)
    
    if (' ' in loc) :
        splitted    = loc.split()
        first       = splitted[0]
        second      = splitted[1]
        locnew      = ("{}%20{}".format(first,second))
    else :
        locnew = loc

    url = "https://nominatim.openstreetmap.org/search/"+locnew+"?format=json&addressdetails=1&limit=1"
    print(url)

    data = requests.get(url=url).text
    data = json.loads(data)
    
    if ('putrajaya' in loc) :
        minlat, minlon, maxlat, maxlon = "2.876833", "2.982444", "101.659687", "101.732682"
        dname = ('{}'.format("Putrajaya"))
    
    else:
        for i in data:
            #bounding = ('{},{},{},{}'.format(i['boundingbox'][0],i['boundingbox'][1],i['boundingbox'][2],i['boundingbox'][3]))
            minlat    = ('{}'.format(i['boundingbox'][0]))
            minlon    = ('{}'.format(i['boundingbox'][1]))
            maxlat    = ('{}'.format(i['boundingbox'][2]))
            maxlon    = ('{}'.format(i['boundingbox'][3]))

            #minlat, minlon, maxlat, maxlon = "2.876833", "2.982444", "101.659687", "101.732682"
            
            dname = ('{}'.format(i['display_name']))
    
    cursor.execute('SELECT privilage FROM user_table WHERE username=?', (username,))
    entry = cursor.fetchone()

    if entry['privilage']==7:
        return redirect(url_for('adminmap', min1=minlat, min2=minlon, max1=maxlat, max2=maxlon, dname=dname))
    elif entry['privilage']==0:
        return redirect(url_for('usermap', min1=minlat, min2=minlon, max1=maxlat, max2=maxlon, dname=dname))
    else :
        return "Error!"

@app.route('/showinv', methods=['POST'])
@flask_login.login_required
def showinv():
    username=flask_login.current_user.id
    splitinv = []
    newlat = []
    newlon = []
    date1 = []
    newalt = []

    date = request.form.get('date') #form

    entry=fetchall_data('SELECT * FROM record_table WHERE datetaken LIKE ?', (date+"%",))

    if entry:
        for row in entry:
            latitude = row['latitude']
            longitude = row['longitude']
            datetaken = row['datetaken']

            newlat.append(latitude)
            newlon.append(longitude)
            date1.append(datetaken)
            

    return render_template('/dash/showinv2.html', list_inv=zip(newlat, newlon, date1))


@app.route('/getAssetUsername', methods=['POST'])
def getAssetUsername():
    if flask_login.current_user.is_authenticated:
        username1 =  request.form['username']
    else:
        return redirect(url_for('login'))

    #username=flask_login.current_user.id

    cursor.execute('SELECT * FROM user_table WHERE status_log=? ', (flask_login.current_user.id,))
    userentry = cursor.fetchone()

    if userentry :
        if userentry['privilage']==7:
            if username1:
                print ("masuk")
                streetlight_userbased = create_marker(username=username1)
                return jsonify({'marker': json.dumps(streetlight_userbased)}), 200 
            else:
                return ('', 204)
        else:
            return redirect(url_for('login'))

#######################################################################################################################################################
########################################################       DASHBOARD MANAGEMENT        ############################################################
#######################################################################################################################################################


user_request = {}

@app.route('/')
def index():
    if flask_login.current_user.is_authenticated:
        username = flask_login.current_user.id
        print(username)
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

        cursor.execute('SELECT * FROM record_table order by datetaken desc limit 5')
        entry2 = cursor.fetchall()

        cursor.execute('SELECT count(*) as count FROM record_table WHERE strftime("%m", datetaken) = strftime("%m", "now")')
        entry4 = cursor.fetchone()

        record = entry4['count']

        cursor.execute('SELECT count(*) as count FROM record_table WHERE strftime("%m", datetaken) = strftime("%m", "now", "-1 months")')
        entry5 = cursor.fetchone()

        pastrecord = entry5['count']

        compare = record - pastrecord

        if entry :
            if entry['privilage']==7:
                return render_template('dash/adminboard.html', username=username, user=entry2, record=record, pastrecord=abs(compare), compare=compare)
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

    cursor.execute('SELECT * FROM record_table WHERE username=? ', (username,))
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

        data_username = entry['username']
        print(data_username)

        cursor.execute('SELECT * FROM record_table order by datetaken desc limit 5')
        entry3 = cursor.fetchall()

        cursor.execute('SELECT count(*) as count FROM record_table WHERE strftime("%m", datetaken) = strftime("%m", "now") AND username=?',(data_username,))
        entry4 = cursor.fetchone()

        record = entry4['count']

        cursor.execute('SELECT count(*) as count  FROM record_table WHERE strftime("%m", datetaken) = strftime("%m", "now", "-1 months") AND username=?',(data_username,))
        entry5 = cursor.fetchone()

        pastrecord = entry5['count']

        compare = record - pastrecord

        if entry :
            if entry['privilage']==0:
                return render_template('dash/dashboard.html', user=entry3, username=data_username, record=record, pastrecord=abs(compare), compare=compare) #user dashboard
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
        reusername = request.form.get('reusername')
        password = request.form.get('password')
        depassword = request.form.get('depassword')
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        address = request.form.get('address')
        repassword = request.form.get('repassword')
        derepassword = request.form.get('derepassword')
        privilage = request.form.get('privilage')
        deprivilage = request.form.get('deprivilage')

        print(username)
        print(password)
        print("Depassword:",format(depassword))
        print(fullname)
        print(email)
        print(address)
        print(privilage)

        if password == " ":
            password = depassword
        if repassword == " ":
            repassword = derepassword
        if privilage == "None" or privilage == "none" :
            privilage = deprivilage

        if password == repassword:
            cursor.execute("UPDATE user_table SET username = ?, fullname = ?, email = ?, address = ?, privilage = ?, password = ? WHERE username = ?", (username,fullname,email,address,privilage,password,reusername))
            flash('You were successfully update user')
            conn.commit()
            cursor.execute("UPDATE record_table SET username = ? WHERE username = ?", (username,reusername))
            conn.commit()
        else:
            flash('Not saved. Please enter the valid password.')

        return redirect(url_for('show_userlist'))

@app.route('/updateitem', methods=['POST'])
@flask_login.login_required
def updateitem():
    if flask_login.current_user.is_authenticated:

        itemname = request.form.get('sameitemname')
        itemid = request.form.get('sameitemid')
        mscode = request.form.get('samemscode')
        #msvalue=""

        print(itemname)
        print(itemid)
        print(mscode)

        changeitemname = request.form.get('itemname')
        changeitemid = request.form.get('itemid')
        changemscode = request.form.get('mscode')
        changemsvalue=""

        print(changeitemname)
        print(changeitemid)

        if changemscode == "0":
            changemsvalue="MS 1500:2009"
        elif changemscode == "1":
            changemsvalue="MS 2200 Part 1:2008"
        elif changemscode == "2":
            changemsvalue="MS 2400-1:2010(P)"
        elif changemscode == "3":
            changemsvalue="MS 2400-2:2010(P)"
        elif changemscode == "4":
            changemsvalue="MS 2400-3:2010(P)"

        print(changemsvalue)
        print(mscode)

        #print ("updateitem msvalue : {}".format(msvalue))

        cursor.execute('SELECT * FROM data_table where itemid=? AND itemname=? AND mscode=?', (itemid,itemname,mscode))
        entry=cursor.fetchone()

        print ("updateitem entry : {}".format(entry))

        if changemscode == "none":
            changemsvalue = mscode

        if entry :            
            #cursor.execute("""UPDATE data_table SET itemid = ?, itemname = ? WHERE mscode = ?""", (itemid,itemname,msvalue))
            cursor.execute("""UPDATE data_table SET itemid = ?, itemname = ?, mscode = ? WHERE itemid = ? AND itemname = ? AND mscode = ?""", (changeitemid,changeitemname,changemsvalue,itemid,itemname,mscode,))
            flash('You were successfully update user')
            conn.commit()
                
            return redirect(url_for('show_itemlist'))
        else:
            flash('Wrong Input')
            return redirect(url_for('show_itemlist'))

        flash('No Item Exist')
        return redirect(url_for('show_itemlist'))

@app.route('/update_userprof', methods=['POST'])
@flask_login.login_required
def update_userprof():
    if flask_login.current_user.is_authenticated:
        username = request.form.get('username')
        fullname = request.form.get('fullname')
        address = request.form.get('address')
        password = request.form.get('password')
        repassword = request.form.get('repassword')
        privilage = request.form.get('privilage')
        deusername = request.form.get('deusername')
        depassword = request.form.get('depassword')

        if password == "":
            password = depassword
            repassword = depassword

        if password == repassword :
            cursor.execute('UPDATE user_table SET password = ?, username = ?, fullname = ?, address = ? WHERE username = ?', (password,username,fullname,address,deusername))
            conn.commit()
            cursor.execute("UPDATE record_table SET username = ? WHERE username = ?", (username,deusername))
            conn.commit()
            flash('You were successfully update password')
        else :
            flash('Password not saved. Try again.')

        print("{} done".format(password))
        print("{} done".format(repassword))
        print("{} done".format(privilage))
        print("{} done".format(username))

        return redirect(url_for('show_userprofile'))

@app.route('/update_adminprof', methods=['POST'])
@flask_login.login_required
def update_adminprof():
    if flask_login.current_user.is_authenticated:
        username = request.form.get('username')
        fullname = request.form.get('fullname')
        address = request.form.get('address')
        password = request.form.get('password')
        repassword = request.form.get('repassword')
        privilage = request.form.get('privilage')
        deusername = request.form.get('deusername')
        depassword = request.form.get('depassword')

        if password == "":
            password = depassword
            repassword = depassword

        if password == repassword :
            cursor.execute('UPDATE user_table SET password = ?, username = ?, fullname = ?, address = ? WHERE username = ?', (password,username,fullname,address,deusername))
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
        inm = request.form.get('itemname')
        ims = request.form.get('mscode')
        print(iid)
        print(inm)
        print(ims)
        
        cursor.execute('SELECT * FROM data_table WHERE itemid=?', (iid,))
        entry = cursor.fetchone()

        if entry:
            cursor.execute('DELETE FROM data_table WHERE itemid=?', (iid,))
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

    if not request.json or not 'itemid' or not 'mscode' or not 'longitude' or not 'latitude' in request.json:
        abort(400)

    item = request.json['itemid']
    ms = request.json['mscode']
    lon = request.json['longitude']
    lat = request.json['latitude']
    user="test"

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

        cursor.execute('INSERT INTO record_table (itemid,itemname,mscode,description,datetaken,username,longitude,latitude) VALUES (?,?,?,?,?,?,?,?)',(item_id,item_name,item_mscode,item_desc,time_act,user,lon,lat))
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

@app.route('/getRecordData', methods=['GET'])
def getRecordData():

    totdata = []
    totdata1 = []
    countdata=[]
    monthdata=[]
    monthdatalabel=[]
    rangetotdata1=0
    try:
        lock.acquire(True)
        cursor.execute('SELECT count(*) as count, strftime("%m", datetaken) as monthdatetaken FROM record_table group by strftime("%m", datetaken)')
        tott = cursor.fetchall()
        for row in tott:
            totdata.append([x for x in row]) # or simply data.append(list(row))
        totdata1 = np.array(totdata)
        rangetotdata1 = len(totdata1)
        for i in range(rangetotdata1):
            countdata.append(totdata1[i][0])
            print(countdata)
            monthdata.append(totdata1[i][1])
            print(monthdata)

        for j in monthdata:
            if j == '1':
                monthdatalabel.append("January")
            elif j == '2':
                monthdatalabel.append("Febuary")
            elif j == '3':
                monthdatalabel.append("March")
            elif j == '4':
                monthdatalabel.append("April")
            elif j == '5':
                monthdatalabel.append("May")
            elif j == '6':
                monthdatalabel.append("June")
            elif j == '7':
                monthdatalabel.append("July")
            elif j == '8':
                monthdatalabel.append("August")
            elif j == '9':
                monthdatalabel.append("September")
            elif j == '10':
                monthdatalabel.append("October")
            elif j == '11':
                monthdatalabel.append("November")
            elif j == '12':
                monthdatalabel.append("December")
    finally:
        lock.release()

    return jsonify({'countdata': countdata,'monthdata': monthdata,'monthdatalabel': monthdatalabel}), 200 

@app.route('/getUserRecordData', methods=['GET'])
def getUserRecordData():

    username=flask_login.current_user.id
    cursor.execute('SELECT * FROM user_table where status_log=?',(username,))
    entry = cursor.fetchone()

    data_username = entry['username']

    totdata = []
    totdata1 = []
    countdata=[]
    msdata=[]
    rangetotdata1=0
    try:
        lock.acquire(True)
        cursor.execute('SELECT count(*) as count, mscode FROM record_table where username=? group by mscode order by mscode asc',(data_username,))
        tott = cursor.fetchall()
        for row in tott:
            totdata.append([x for x in row]) # or simply data.append(list(row))
        totdata1 = np.array(totdata)
        rangetotdata1 = len(totdata1)
        for i in range(rangetotdata1):
            countdata.append(totdata1[i][0])
            print(countdata)
            msdata.append(totdata1[i][1])
            print(msdata)
    finally:
        lock.release()

    return jsonify({'countdata': countdata,'msdata': msdata}), 200 
  
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
