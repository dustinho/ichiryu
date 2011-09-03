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
#for the mtg card database
import json

# twisted imports
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol
from twisted.python import log

# system imports
import time, sys
import re
import pickle

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
    return int(url[url.rfind('/')+1:url.rfind('_')])

OMP_REGEX = re.compile("http://ompl(oade)|dr\\.org/[a-zA-Z0-9]{5,8}($|[^a-zA-Z0-9])")
OMP_LINK = "http://omploader.org/vMmhmZA"
OMP_LINK_REGEX = re.compile("http://omploa(oade)|der\\.org/vMmhmZA($|[^a-zA-Z0-9])")

#MTG card dict.  if there's a pickled copy, load that instead and use it
try:
    mtg = pickle.load(open('mtg.pickle','r'))
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
        # There's a card with no name
        if card_name == '':
            continue
        # only keep the card with the largest url number
        if (card_name not in mtg_links or 
            (urlnumber(card_url) > urlnumber(mtg_links.get(card_name)))):
            mtg_links[card_name] = card_url
            if len(card_name) > max_card_name_length:
                max_card_name_length = len(card_name)
    mtg = {'max card name length':max_card_name_length,'mtg links':mtg_links}
    pickle.dump(mtg,open('mtg.pickle','w'))

channel = "#wonted" # Make sure this has a hash prepended
logroot = "/home/dustin/ichiryu/wonted-logs/"

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

    nickname = "IchiryuBot"
    nicknames = ("IchiryuBot", "Ichiryu", "ichiryu", "ichiryubot")

    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        self.logger = MessageLogger(self.factory.logroot, self.factory.channel)
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

        # imo.im
        if msg.endswith("imo"):
            self.say(channel, ".im")

        # Respond to ompldr links other than this one with this one.
        if len(re.findall(OMP_REGEX,msg)) > len(re.findall(OMP_LINK_REGEX,msg)):
            self.say(channel, "%s: %s" % (user, OMP_LINK))

        # If a message ends with a magic card name, return url to picture
        stripped_chars = charstrip(msg, max_card_name_length)
        for i in range(len(stripped_chars)):
            if stripped_chars[i:] in mtg_links:
                self.say(channel, 
                         "%s: %s" % (user, mtg_links.get(stripped_chars[i:])))
                break # so we only say the longest one

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
        self.logger.log("%s is now known as %s" % (old_nick, new_nick))


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

    def __init__(self, channel, logroot):
        self.channel = channel
        self.logroot = logroot

    def clientConnectionLost(self, connector, reason):
        """If we get disconnected, reconnect to server."""
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        print "connection failed:", reason
        reactor.stop()


if __name__ == '__main__':
    # initialize logging
    log.startLogging(sys.stdout)

    # create factory protocol and application
    f = LogBotFactory(channel, logroot)

    # connect factory to this host and port
    reactor.connectTCP("irc.rizon.net", 6667, f)

    # run bot
    reactor.run()
