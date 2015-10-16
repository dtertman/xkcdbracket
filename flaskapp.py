from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash
import MySQLdb
import os
import httplib
import urllib
import json
import datetime;
import string;

db_host=os.environ.get('OPENSHIFT_MYSQL_DB_HOST','localhost')
db_port=int(os.environ.get('OPENSHIFT_MYSQL_DB_PORT','3306'))
db_user=os.environ.get('OPENSHIFT_MYSQL_DB_USERNAME','xkcdbracket')
db_pass=os.environ.get('OPENSHIFT_MYSQL_DB_PASSWORD','xkcdbracket')
db_db="xkcdbracket"

#add recaptcha public and private here

admin_user='xkcdbracketadmin'
admin_pass='changeme'

app = Flask(__name__)



class Game:

    def __init__(self,id,name,start,end):
        self.id = id;
        self.name = name;
        self.start = start;
        self.end = end;
        self.entrants = []
        
    def addGameEntrant(self,gameEntrant):
        self.entrants.append(gameEntrant);
        
    def getEntrantById(self,entrantId):
        for entrant in self.entrants:
            if (entrant.entrant.id == entrantId):
                return entrant;
        return None;
    
class Entrant:
    
    def __init__(self,id,name):
        self.id = id
        self.name = name
       
class GameEntrant:
    def __init__(self,entrant):
        self.entrant = entrant;
        self.votes = 0;
              

def connect_db():
  return MySQLdb.connect(host=db_host,user=db_user,passwd=db_pass,port=db_port,db=db_db)
  
def getCurrentGames(db):
    gamecur = db.cursor()
    entrantcur = db.cursor()
    games = []
    now = datetime.datetime.now()
    gamecur.execute("select id, name, start, end from game where start < %s and end > %s",(now,now));
    for row in gamecur:
        game = Game(id=row[0],name=row[1],start=row[2],end=row[3])
        games.append(game)
        entrantcur.execute("select e.id, e.name, ge.votes from entrant e, game_entrant ge where e.id = ge.entrant_id and ge.game_id = %s",[game.id])
        for entrantrow in entrantcur:
            entrant = Entrant(entrantrow[0],entrantrow[1])
            gameentrant = GameEntrant(entrant)
            gameentrant.votes = entrantrow[2]
            game.addGameEntrant(gameentrant);
    gamecur.close()
    entrantcur.close()
    return games

def verifyCaptcha():
    addr = request.remote_addr;

    response = request.form["g-recaptcha-response"];

    params = urllib.urlencode({'secret':recaptchaPrivate,'response':response,'remoteip':addr})
    conn = httplib.HTTPSConnection("www.google.com");
    conn.request("POST","/recaptcha/api/siteverify?" + params,"",{"Content-length":0});
    response = conn.getresponse()
    respJson = json.loads(response.read())
    conn.close()
    return str(respJson["success"])  

def getGame(gameId, games=None):
    if (games == None):
        db = getattr(g, 'db', None)
        games = getCurrentGames(db)
    for game in games:
        if (game.id == gameId):
            return game;
    return None;
    
def getEntrants(db=None):
    if (db == None):
        db = getattr(g, 'db', None);
    cursor = db.cursor();
    cursor.execute("SELECT ID, NAME FROM entrant ORDER BY name");
    entrants = []
    for id, name in cursor:
        entrants.append(Entrant(id,name))
    cursor.close()
    return entrants;
    
def decodeDates(startText, endText):
    if (startText == ""):
        startDate = datetime.datetime.now()
    else :
        startDate = datetime.datetime.strptime(startText,"%Y-%m-%d")
    
    if (endText == ""):
        timedelta = datetime.timedelta(days=1)
        endDate = datetime.datetime.now() + timedelta
    else :
        endDate = datetime.datetime.strptime(endText,"%Y-%m-%d")
    startDate = startDate.replace(hour=0,minute=0,second=0,microsecond=0)
    endDate = endDate.replace(hour=0,minute=0,second=0,microsecond=0)
    return (startDate, endDate)
              
@app.before_request
def before_request():
    g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()

@app.route('/')
def home():
    db = getattr(g, 'db', None)
    games = getCurrentGames(db);
    if 'votedGameId' in request.args:
        game = getGame(int(request.args['votedGameId']),games)
        if (game != None):
            game.voted = True;
            entrant = game.getEntrantById(int(request.args['votedEntrantId']))
            if (entrant != None):
                game.votedEntrant = entrant.entrant.name;
    return render_template('home.html',games=games)
    
@app.route('/processVote',methods=['GET','POST'])
def processVote():
    if (verifyCaptcha()):
        gameId = int(request.form["gameId"])
        game = getGame(gameId)
        if (game != None):
                entrantId = int(request.form["entrantId"])
                entrant = game.getEntrantById(entrantId)
                if (entrant != None):
                    db = getattr(g, 'db', None)
                    updateCursor = db.cursor();
                    rows = updateCursor.execute("UPDATE game_entrant SET votes = votes + 1 WHERE game_id=%s AND entrant_id=%s",[gameId, entrantId])
                    if (rows == 1):
                        db.commit();
                    else:
                        db.rollback();
                    updateCursor.close();           
        return redirect(url_for('home')+"?votedGameId="+str(gameId)+"&votedEntrantId="+str(entrantId))
    else:
        return redirect(url_for('home'))

@app.route('/login',methods=['GET'])
def getLoginPage():
    return render_template('login.html');

@app.route('/login',methods=['POST'])
def postLoginPage():
    username = request.form['username']
    password = request.form['password']
    if (username != admin_user or password != admin_pass):
        return redirect(url_for('getLoginPage'))
    else:
        session["loggedIn"] = True
        return redirect(url_for('getSchedulePage'))
        
@app.route('/logout')
def logout():
    session.pop("loggedIn",None)
    return redirect(url_for('home'))
        
@app.route('/schedule',methods=['GET'])
def getSchedulePage():
    if ('loggedIn' in session and session["loggedIn"]):
        entrants = getEntrants()
        failed = request.args['failed']=='True' if 'failed' in request.args else None
        return render_template('schedule.html',scheduleActive="active",title="Schedule",entrants=entrants,failed=failed);
    else:
        return redirect(url_for('getLoginPage'))

@app.route('/schedule', methods=['POST'])
def postGame():
    if ('loggedIn' in session and session["loggedIn"]):
        db = getattr(g, 'db', None)
        entrants = getEntrants(db)
        selectedEntrants = request.form.getlist("entrants")
        gameName = request.form["gameName"] if 'gameName' in request.form else ""
        startText= request.form["gameStart"] if 'gameStart' in request.form else ""
        endText = request.form["gameEnd"] if 'gameEnd' in request.form else ""
        validEntrants = []
        entrantNames = []
        for id in selectedEntrants:
            for entrant in entrants:
                if int(id) == entrant.id:
                    if gameName == "":
                        entrantNames.append(entrant.name)
                    validEntrants.append(id)
                    break;
        if (gameName == ""):
            gameName = string.join(entrantNames, " vs ")
        
        startDate, endDate = decodeDates(startText, endText);
        gameCursor = db.cursor();
        rows = gameCursor.execute("Insert into game (id, name, start, end) select max(id+1), %s, %s, %s from game",[gameName,startDate,endDate])
        failed = rows != 1;
        if (not failed):
            gameCursor.execute("select max(id) from game")
            gameId = gameCursor.fetchone()[0]
            for id in validEntrants:
                rows = gameCursor.execute("insert into game_entrant (game_id, entrant_id, votes) values (%s,%s,0)",[gameId,id]);
                if (rows != 1):
                    failed = True
                    break;
        if (failed):
            db.rollback();
        else:
            db.commit();
        gameCursor.close();
        
        return redirect(url_for('getSchedulePage') + "?failed=" + str(failed));
    else:
        return redirect(url_for('getLoginPage'))
        
@app.route('/upcoming',methods=['GET'])
def getUpcomingPage():
    if ('loggedIn' in session and session["loggedIn"]):
        return render_template('upcoming.html',upcomingActive="active",title="Upcoming");
    else:
        return redirect(url_for('getLoginPage'))        

@app.route('/results',methods=['GET'])
def getResultsPage():
    if ('loggedIn' in session and session["loggedIn"]):
        return render_template('results.html',resultsActive="active",title="Results");
    else:
        return redirect(url_for('getLoginPage'))


@app.route('/admin',methods=['GET'])
def redirectToSchedule():
    return redirect(url_for('getSchedulePage'));
    



if __name__ == '__main__':
    app.run(debug=True)
