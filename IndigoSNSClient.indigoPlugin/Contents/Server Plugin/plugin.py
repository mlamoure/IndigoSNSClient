import sys
import os
import inspect
import cgi
import re
import urllib
import urllib2
import getopt
import urlparse
import time
import simplejson
import BaseHTTPServer
import NATPMP
from boto.sns.connection import SNSConnection
from boto.s3.connection import S3Connection
from boto.s3.key import Key
import AmazonSNShttpServerHandler
import threading
import Queue
import IndigoPluginHelper

class Plugin(indigo.PluginBase):
	pluginHelper = None
	server_thread = None
	server = None
	server_runwhiletrue = True
	NATRefresh = 21600

	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)


	def startup(self):
		self.loadConfiguration()

		self.server_runwhiletrue = True
		self.startHTTPServer(int(self.pluginHelper.private_port), self.pluginHelper)

	def schedulePortForwardingRefresh(self):
		indigo.server.log("Scheduled another refresh of NAT PMP in " + str(self.NATRefresh) + " seconds")
		threading.Timer(self.NATRefresh - 5, self.performPortForwardingRefresh).start()

	def performPortForwardingRefresh(self):
		try:
			indigo.server.log("Requesting NAT PMP port forwarding from router for public port " + str(self.pluginHelper.private_port) + " to private port " + str(self.pluginHelper.private_port))
			NATPMP_result = NATPMP.map_port(NATPMP.NATPMP_PROTOCOL_TCP, int(self.pluginHelper.public_port), int(self.pluginHelper.private_port), self.NATRefresh, gateway_ip=self.pluginHelper.gatewayIP)

			if self.pluginHelper.debug:
				indigo.server.log("NAT PMP Response: " + str(NATPMP_result))

			self.schedulePortForwardingRefresh()
		except:
			indigo.server.log("There was a problem with the NAT PMP process.  Check your configuration.")


	def loadConfiguration(self):
		awsAccessKeyID = self.pluginPrefs.get("awsAccessKeyID", "")
		awsSecretAccessKey = self.pluginPrefs.get("awsSecretAccessKey", "")

		if (len(awsSecretAccessKey) == 0 or len(awsSecretAccessKey) == 0): return

		self.stop = False
		self.pluginHelper = IndigoPluginHelper.IndigoPluginHelper()

		self.pluginHelper.indigo = indigo
		self.pluginHelper.debug = bool(self.pluginPrefs.get("debug", self.pluginPrefs.get("debug", "False")))

		self.pluginHelper.s3Connection = S3Connection(awsAccessKeyID, awsSecretAccessKey)
		self.pluginHelper.snsConnection = SNSConnection(awsAccessKeyID, awsSecretAccessKey, validate_certs=False)

		self.pluginHelper.public_port = self.pluginPrefs.get("serverPublicPort", 60150)
		self.pluginHelper.private_port = self.pluginPrefs.get("serverPrivatePort", 60150)
		self.pluginHelper.gatewayIP = self.pluginPrefs.get("gatewayIP", "")
		self.pluginHelper.publicIP = self.pluginPrefs.get("publicIP", "")

		if self.pluginPrefs["useNATPMP"]:
			if len(self.pluginHelper.gatewayIP) == 0:
				self.pluginHelper.gatewayIP = NATPMP.get_gateway_addr()

			self.performPortForwardingRefresh()

		if len(self.pluginHelper.publicIP) == 0:
			self.pluginHelper.publicIP = urllib2.urlopen('http://ip.42.pl/raw').read()

			if self.pluginHelper.debug: 
				indigo.server.log("Looked up public IP Address and resolved to " + self.pluginHelper.publicIP)

		self.pluginHelper.snsEndpointURL = "http://" + self.pluginHelper.publicIP + ":" + str(self.pluginHelper.public_port);
		self.pluginHelper.localEndpointURL = "http://localhost:" + str(self.pluginHelper.public_port)
		if self.pluginHelper.debug: indigo.server.log("SNS Endpoint URL is set to " + self.pluginHelper.snsEndpointURL)

	def unSubscribeToTopic(self, topic):
		if not self.pluginHelper.amSubscribed(topic):
			topic.updateStateOnServer("status", value="unknown")
			return

		topicArn = topic.pluginProps["snsTopicArn"]
		subscription = self.pluginHelper.getSubscription(topicArn)

		topic.updateStateOnServer("status", value="notsubscribed")

		indigo.server.log("Un-subscribing to topic: " + topicArn + " with subscription ID: " + subscription)
		
		self.pluginHelper.snsConnection.unsubscribe(subscription)
		self.pluginHelper.clearSubscription(topicArn)

		amSubscribed = self.pluginHelper.amSubscribed(topic)

		if self.pluginHelper.debug: 
			self.pluginHelper.indigo.server.log("isConfirmed status for : " + topicArn + " is now: " + str(amSubscribed))

	def subscribeToTopic(self, topic):
		topicArn = topic.pluginProps["snsTopicArn"]
		if self.pluginHelper.amSubscribed(topic):
			if self.pluginHelper.debug: indigo.server.log("Already subscribed to topic: " + topicArn + " not going to do anything more.")
			topic.updateStateOnServer("status", value="unknown")
			return False

		topic.updateStateOnServer("status", value="requested")

		indigo.server.log("Subscribing to topic: " + topicArn + " with endpoint: " + self.pluginHelper.snsEndpointURL)

		if self.pluginHelper.snsEndpointURL[:5] == "https":
			self.pluginHelper.snsConnection.subscribe(topicArn, "https", self.pluginHelper.snsEndpointURL)
		elif self.pluginHelper.snsEndpointURL[:4] == "http":
			self.pluginHelper.snsConnection.subscribe(topicArn, "http", self.pluginHelper.snsEndpointURL)
		return True

	def stopHTTPServer(self):
		# Ping the server to wake it up.	
		self.server_runwhiletrue = False
		try:
			values = {"Shutdown":"True"}
			data = urllib.urlencode(values)
			req = urllib2.Request(self.pluginHelper.localEndpointURL, data)
			urllib2.urlopen(req)
			self.server_thread = None
			self.server = None

		except Exception:
			indigo.server.log("Found that the server was not running")

	def startHTTPServer(self, port, pluginHelper):
		indigo.server.log("SNS Endpoint Server started on local port " + str(port))	
		self.server = AmazonSNShttpServerHandler.ThreadedHTTPServer(("",port), lambda *args: AmazonSNShttpServerHandler.AmazonSNShttpServerHandler(pluginHelper, *args))
		self.server_thread = threading.Thread(target=self.startWhileRunningHTTPServer).start()

	def startWhileRunningHTTPServer(self):
		while self.server_runwhiletrue:
			self.server.handle_request()

	def unsubscribeAllTopics(self):
		for topic in self.pluginHelper.getAllSNSTopics():
			if self.pluginHelper.amSubscribed(topic):
				self.unSubscribeToTopic(topic)
		return

	def subscribeAllTopics(self):
		for topic in self.pluginHelper.getAllSNSTopics():
			if not self.pluginHelper.amSubscribed(topic):
				self.subscribeToTopic(topic)
		return

	def shutdown(self):
		if self.pluginHelper.debug:
			indigo.server.log("Running shutdown")
		self.stopHTTPServer()
		self.unsubscribeAllTopics()
		return

	def __del__(self):
		indigo.PluginBase.__del__(self)

# Configuration
	def closedPrefsConfigUi(self, valuesDict, userCancelled):
		indigo.server.log("Reloading configuration")
		self.shutdown()
		self.clearConfiguration()
		time.sleep(5)
		self.startup()
		self.subscribeAllTopics()
		return

	def clearConfiguration(self):
		indigo.server.log("Clearing configuration")
		self.pluginHelper = None
		return

# Devices
	def deviceStartComm(self, dev):
		if not self.pluginHelper.isConfigured():
			indigo.server.log("The plugin is not properly configured, so devices cannot init.")
			return

		if dev.deviceTypeId == "SNSTopic":
			topicArn = dev.pluginProps["snsTopicArn"]
			if self.pluginHelper.debug: indigo.server.log("Initializing device: " + topicArn + ", amSubscribed(): " + str(self.pluginHelper.amSubscribed(dev)))

			if self.pluginHelper.amSubscribed(dev):
				dev.updateStateOnServer("status", value="unknown")
				if self.pluginHelper.debug: 
					indigo.server.log("Already subscribed to topic: " + topicArn + " not going to do anything more.")
			else:
				self.subscribeToTopic(dev)
		
		elif dev.deviceTypeId == "location":
			dev.updateStateOnServer("distance", value=0)

		elif dev.deviceTypeId == "SNSDevice":
			dev.updateStateOnServer("nearestLocation", value="Unknown")
		return

	def deviceStopComm(self, dev):
		if not self.pluginHelper.isConfigured():
			indigo.server.log("The plugin is not properly configured, so devices cannot init.")
			return

		if dev.deviceTypeId == "SNSTopic":
			topicArn = dev.pluginProps["snsTopicArn"]
			if self.pluginHelper.debug: indigo.server.log("Deinitializing device: " + topicArn)

			if (self.pluginHelper.amSubscribed(dev)):
				self.unSubscribeToTopic(dev)
			else:
				dev.updateStateOnServer("status", value="unknown")
				if self.pluginHelper.debug: 
					indigo.server.log("Not subscribed to topic: " + topicArn + " not going to do anything more.")
		
		elif dev.deviceTypeId == "SNSDevice":
			dev.updateStateOnServer("nearestLocation", value="Unknown")
		
		elif dev.deviceTypeId == "location":
			dev.updateStateOnServer("distance", value=0)
		return

	def didDeviceCommPropertyChange(self, origDev, newDev):
		if origDev.deviceTypeId == "SNSTopic":
			if origDev.pluginProps['snsTopicArn'] != newDev.pluginProps['snsTopicArn']:
				return True

		elif origDev.deviceTypeId == "location":
			if origDev.pluginProps['latitude'] != newDev.pluginProps['latitude'] or origDev.pluginProps['longitude'] != newDev.pluginProps['longitude']:
				return True

		return False

# DEVICES.XML Methods

	def getSNSTopicFields(self, valuesDict):
		if valuesDict == None:
			return [("Please select a Topic above", "Please select a Topic above")]

		if "snsTopic" in valuesDict:
			try:
				selectedTopic = indigo.devices[int(valuesDict["snsTopic"])]
			except ValueError:
				return [("Please select a Topic above", "Please select a Topic above")]
			
			if not "knownKeys" in selectedTopic.pluginProps:
				return [("No known keys", "No known keys")]

			keysList = []

			for key in selectedTopic.pluginProps["knownKeys"]:
				if not "," in key and len(key) > 1:
					keysList.append((key, key))

			if len(keysList) == 0:
				keysList = [("No known keys", "No known keys")]

			return keysList

		return [("Please select a Topic above", "Please select a Topic above")]

	def refreshFields(self, valuesDict, typeId, devId):
		return valuesDict

	def getTopicFieldGenerator(self, filter="", valuesDict=None, typeId="", targetId=0):
		knownFields = self.getSNSTopicFields(valuesDict)
		if targetId > 0:
			if filter in indigo.devices[targetId].pluginProps:
				if not indigo.devices[targetId].pluginProps[filter] in knownFields:
					if len(knownFields) == 1:
						knownFields = [(indigo.devices[targetId].pluginProps[filter], indigo.devices[targetId].pluginProps[filter])]
					else:
						knownFields.append((indigo.devices[targetId].pluginProps[filter], indigo.devices[targetId].pluginProps[filter]))
		return knownFields

#	def topicFieldListGenerator(self, filter="", valuesDict=None, typeId="", targetId=0):
#		return myArray