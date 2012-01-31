# COPYRIGHT (C) 2001-2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An example IRC log bot - logs a channel's events to a file.

If someone says the bot's name in the channel followed by a ':',
e.g.

  <foo> logbot: hello!

the bot will reply:

  <logbot> foo: I am a log bot

Run this script with two arguments, the channel name the bot should
connect to, and file to log to, e.g.:

  $ python ircLogBot.py test test.log

will log channel #test to the file 'test.log'.
"""

# twisted imports
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol
from twisted.python import log

# system imports
import time, sys
import re
import pickle, json, yaml
import twitter

# for lua bot like functionality
import subprocess

# A function to strip non alpha-numerics from the end of a string, keep only
# max_length characters from the end (after stripping), and make everything
# lower case.  This will be used on both the magic dict and incoming messages
def charstrip(string, max_length=False):
    stripped_string = ''
    for char in string[::-1]:
        if (stripped_string != '' and
            (len(stripped_string) < max_length or max_length == False)):
            stripped_string = char + stripped_string
        if char.isalpha() and stripped_string == '':
            stripped_string = char
    return stripped_string.lower()

# A function that takes a url from cardkingdom.com, and strips out the
# identifying number (bigger is generally newer), returning that number
# as an int
def urlnumber(url):
    return int(url[url.rfind('/') + 1:url.rfind('_')])

OMP_REGEX = re.compile("http://ompl(oade)|dr\\.org/[a-zA-Z0-9]{5,8}($|[^a-zA-Z0-9])")
OMP_LINK = "http://omploader.org/vMmhmZA"
OMP_LINK_REGEX = re.compile("http://omploa(oade)|der\\.org/vMmhmZA($|[^a-zA-Z0-9])")
MAX_LUA_OUTPUT = 322

TWITTER_LINK = "http://twitter.com/#!/thnkabtitluse"

try:
    twitter_info = yaml.load(open("twitter_info.json"))
    api = twitter.Api(consumer_key = twitter_info["consumer_key"],
                      consumer_secret = twitter_info["consumer_secret"],
                      access_token_key = twitter_info["access_token_key"],
                      access_token_secret = twitter_info["access_token_secret"])
except:
    print "File twitter_info.json not found or incomplete."
                  

# MTG card dict.  if there's a pickled copy, load that instead and use it
try:
    mtg = pickle.load(open('mtg.pickle'))
    max_card_name_length = mtg['max card name length']
    mtg_links = mtg['mtg links']
except:
    mtg_json = open("mtg_cards.json")
    big_mtg_dict = json.load(mtg_json)
    max_card_name_length = 0
    mtg_links = {}
    for mtg_card in big_mtg_dict:
        card_name = charstrip(str(mtg_card['name']))
        card_url = str(mtg_card['imgUrl'])
        # only keep the card with the largest url number
        if (card_name not in mtg_links or
            (urlnumber(card_url) > urlnumber(mtg_links.get(card_name)))):
            mtg_links[card_name] = card_url
            if len(card_name) > max_card_name_length:
                max_card_name_length = len(card_name)
    mtg = {'max card name length':max_card_name_length,'mtg links':mtg_links}
    pickle.dump(mtg,open('mtg.pickle','w'))

# ASCII art dict.
ascii_json = open("ascii_art.json")
big_ascii_dict = json.load(ascii_json)
ascii_text = {}
for art in big_ascii_dict:
    art_name = charstrip(str(art['name']))
    art_text = str(art['text'])
    ascii_text[art_name] = art_text

class MessageLogger:
    """
    An independent logger class (because separation of application
    and protocol logic is a good thing).
    """
    def __init__(self, logroot, channel):
        # Open initial log file
        self.logroot = logroot
        self.channel = channel
        self.datestamp = time.strftime("%Y-%m-%d", time.localtime(time.time()))
        self.file = open(self.logroot + self.logfile(), "a")

    def log(self, message):
        """Write a message to the file."""
        # Check if we're on a new date
        datestamp = time.strftime("%Y-%m-%d", time.localtime(time.time()))
        if datestamp != self.datestamp:
            self.datestamp = datestamp
            self.file.close()
            self.file = open(self.logroot + self.logfile(), "a")

        timestamp = time.strftime("[%H:%M:%S]", time.localtime(time.time()))
        self.file.write('%s %s\n' % (timestamp, message))
        self.file.flush()

    def logfile(self):
        """ Generates the current log file name, path not included"""
        # Note that the hash mark is stripped from the channel
        return self.datestamp + "-" + self.channel[1:] + ".log"

    def loglink(self):
        """ Generate the http link to the logfile """
        return "http://www.dustinho.com/wonted-logs/" + self.logfile()

    def close(self):
        self.file.close()


class LogBot(irc.IRCClient):
    """A logging IRC bot."""

    # Load Configuration File
    config = yaml.load(open('config.json'))
    nickname = config["nickname"]
    nicknames = tuple(config["nicknames"])
    user_to_last_msg = {}

    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        self.logger = MessageLogger(self.factory.logroot,
                                    self.factory.channel)
        self.logger.log("[connected at %s]" %
                        time.asctime(time.localtime(time.time())))

    def connectionLost(self, reason):
        irc.IRCClient.connectionLost(self, reason)
        self.logger.log("[disconnected at %s]" %
                        time.asctime(time.localtime(time.time())))
        self.logger.close()


    # callbacks for events

    def signedOn(self):
        """Called when bot has succesfully signed on to server."""
        print self.factory.channel
        self.join(self.factory.channel)

    def joined(self, channel):
        """This will get called when the bot joins the channel."""
        self.logger.log("[I have joined %s]" % channel)

    def privmsg(self, user, channel, msg):
        """This will get called when the bot receives a message."""
        user = user.split('!', 1)[0]

        # Check to see if they're sending me a private message
        if channel == self.nickname:
            msg = "It isn't nice to whisper!  Play nice with the group."
            self.msg(user, msg)
            return

        if channel != self.factory.channel:
            return

        # Log messages in the channel
        self.logger.log("<%s> %s" % (user, msg))

        # This bot is also lua_bot
        if msg.startswith("lua>"):
            lua_file = open("lua_in.lua", "w")
            lua_file.write(msg[4:])
            lua_file.close()
            lua_guy = subprocess.Popen(["./sandbox.sh"], shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            response = lua_guy.stdout.read(MAX_LUA_OUTPUT*3)
            err_output = lua_guy.stderr.read(MAX_LUA_OUTPUT*3)
            if err_output:
                if err_output.startswith("./sandbox.sh: line 3:"):
                    response = "Your code exceeded set CPU limits"
                else:
                    response = "Error: " + err_output
            response = response.replace("\t","")
            response = ", ".join([x for x in response.split("\n") if x])
            if len(response) > MAX_LUA_OUTPUT:
                response = (response[:MAX_LUA_OUTPUT-22] +
                        "... (result truncated)")
            self.say(channel, "%s: %s" % (user, response))
            lua_guy.kill()
            return

        # Regex find and replace
        tokens = msg.split("/")
        if len(tokens) == 3 or len(tokens) == 4:
            who = tokens[0]
            if who == "s":
                who = user
            prev_msg = self.user_to_last_msg.get(who)
            if prev_msg:
                new_msg = re.sub(tokens[1], tokens[2], prev_msg)
                self.say(channel, "%s meant to say: %s" % (who, new_msg))
                self.user_to_last_msg[who] = new_msg
        else:
            self.user_to_last_msg[user] = msg

        # imo.im
        if msg.endswith("imo"):
            self.say(channel, ".im")

        # Twitter
        if "#thinkaboutitluse" in msg:
            if len(msg) > 140:
                self.say(channel, 
                         "I'm sorry %s, that Tweet is too long." % (user))
            else:
                status = api.PostUpdate(msg)
                self.say(channel, 
                         "%s: Tweet posted! Check it out at %s" 
                         % (user, TWITTER_LINK))

        # Respond to ompldr links other than this one with this one.
        if len(re.findall(OMP_REGEX,msg)) > len(re.findall(OMP_LINK_REGEX,msg)):
            self.say(channel, "%s: %s" % (user, OMP_LINK))

        # If a message ends with a magic card name, return url to picture
        stripped_chars = charstrip(msg, max_card_name_length)
        for i in range(len(stripped_chars) - 2): # minimum of 3-character match
            if stripped_chars[i:] in mtg_links:
                self.say(channel,
                         "%s: %s" % (user, mtg_links.get(stripped_chars[i:])))
                break # so we only say the longest one

        # Ship it.
        if charstrip(msg).endswith("ship it"):
            self.say(channel, ascii_text["ship"])

        # Otherwise check to see if it is a message directed at me
        if msg.startswith(self.nicknames):
            loglink = self.logger.loglink()
            my_msg = "%s: Logs can be found at % s" % (user, loglink)
            self.say(channel, my_msg)

    def say(self, channel, msg):
        self.msg(channel, msg)
        self.logger.log("<%s> %s" % (self.nickname, msg))

    def action(self, user, channel, msg):
        """This will get called when the bot sees someone do an action."""
        user = user.split('!', 1)[0]
        self.logger.log("* %s %s" % (user, msg))

    # irc callbacks

    def irc_NICK(self, prefix, params):
        """Called when an IRC user changes their nickname."""
        old_nick = prefix.split('!')[0]
        new_nick = params[0]
        self.logger.log(
            "%s is now known as %s (%s)" % (old_nick, new_nick, prefix))

    def irc_TOPIC(self, prefix, params):
        """Called when someone in the channel sets the topic"""
        user = prefix.split('!')[0]
        newtopic = params[1]
        self.logger.log(
            "%s set the topic to %s (%s)" % (user, newtopic, prefix))

    def irc_JOIN(self, prefix, params):
        """Called when someone joins a channel."""
        nick = prefix.split('!')[0]
        channel = params[-1]
        if nick == self.nickname:
            self.joined(channel)
        else:
            self.logger.log("%s has joined %s (%s)" % (nick, channel, prefix))

    def irc_PART(self, prefix, params):
        """Called when a user leaves a channel."""
        nick = prefix.split('!')[0]
        channel = params[0]
        self.logger.log("%s has left %s (%s)" % (nick, channel, prefix))

    def irc_QUIT(self, prefix, params):
        """Called when a user has quit."""
        nick = prefix.split('!')[0]
        self.logger.log("%s has quit [%s] (%s)" % (nick, params[0], prefix))

    def irc_KICK(self, prefix, params):
        """Called when a user is kicked from a channel."""
        kicker = prefix.split('!')[0]
        channel = params[0]
        kicked = params[1]
        message = params[-1]
        self.logger.log(
            "%s was kicked by %s (%s) for reason [%s]" % 
            (kicked, kicker, prefix, message))

    # For fun, override the method that determines how a nickname is changed on
    # collisions. The default method appends an underscore.
    def alterCollidedNick(self, nickname):
        """
        Generate an altered version of a nickname that caused a collision in an
        effort to create an unused related name for subsequent registration.
        """
        return nickname + '^'



class LogBotFactory(protocol.ClientFactory):
    """A factory for LogBots.

    A new protocol instance will be created each time we connect to the server.
    """

    # the class of the protocol to build when new connection is made
    protocol = LogBot

    def __init__(self, channel, logroot, nickname, nicknames):
        self.channel = channel
        self.logroot = logroot
        self.nickname = nickname
        self.nicknames = nicknames

    def clientConnectionLost(self, connector, reason):
        """If we get disconnected, reconnect to server."""
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        print "connection failed:", reason
        reactor.stop()


if __name__ == '__main__':
    # Load Configuration File
    config = yaml.load(open('config.json'))
    nickname = config["nickname"]
    nicknames = tuple(config["nicknames"])
    channel = config["channel"]
    logroot = config["logroot"]
    server = config["server"]
    port = config["port"]

    # initialize logging
    log.startLogging(sys.stdout)

    # create factory protocol and application
    f = LogBotFactory(channel, logroot, nickname, nicknames)

    # connect factory to this host and port
    reactor.connectTCP(server, port, f)

    # run bot
    reactor.run()
