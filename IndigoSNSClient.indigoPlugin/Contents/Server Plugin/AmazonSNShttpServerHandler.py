# -*- coding: utf-8 -*-
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
import threading
import sys
import Queue
import simplejson
import IndigoPluginHelper
import traceback
from boto.sns.connection import SNSConnection
from boto.s3.connection import S3Connection
from boto.s3.key import Key

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
	pass

class AmazonSNShttpServerHandler(BaseHTTPRequestHandler):
	pluginHelper = None

	def __init__(self, pluginHelper, *args):
		self.pluginHelper = pluginHelper

		BaseHTTPRequestHandler.__init__(self, *args)

	def do_POST(self):
		try:
			response = "Nothing to see here."
			self.send_response(200)
			self.send_header('Content-type', 'text/html')		
			self.send_header( "Content-length", str(len(response)) )
			self.end_headers()
			self.wfile.write(response)
			
			length = int(self.headers.getheader('content-length'))

			to_read = length
			body = ''

			while len(body) < length:  
				_req_str = self.rfile.read(to_read)  
				to_read -= len(_req_str)  
				body += _req_str  

			if self.pluginHelper.debug: self.pluginHelper.indigo.server.log("Processing a POST, body: " + body)

			if body[:8].upper() == "SHUTDOWN":
				self.pluginHelper.indigo.server.log("Shutting down the SNS Endpoint Server")
				return

			try:
				bodyJSON = simplejson.loads(body)
			except:
				try:
					self.data_string = self.rfile.read(int(self.headers['Content-Length']))
					bodyJSON = simplejson.loads(str(self.data_string))
				except:
					self.pluginHelper.indigo.server.log("I didn't know how to parse the body message.")

					if self.pluginHelper.debug:
						self.pluginHelper.indigo.server.log("Ignoring Message, headers: ")
						self.pluginHelper.indigo.server.log(str(self.headers))
						self.pluginHelper.indigo.server.log("body: ")
						self.pluginHelper.indigo.server.log(str(body))					
					return

			if "TopicArn" in bodyJSON:
				topicArn = bodyJSON["TopicArn"]

			if bodyJSON["Type"] == "SubscriptionConfirmation":
				topic = self.pluginHelper.getTopic(topicArn)

				if (topic == None):
					self.pluginHelper.indigo.server.log("Received a confirmation token for a topic we are not familiar with.")
					return

				if self.pluginHelper.debug: 
					self.pluginHelper.indigo.server.log("Going to confirm subscription for topic " + topicArn + " with confirmation token: " + bodyJSON['Token'])
				else: self.pluginHelper.indigo.server.log("Confirming subscription for topic " + topicArn)

				response = self.pluginHelper.snsConnection.confirm_subscription(topicArn, bodyJSON["Token"])
				
#				if self.pluginHelper.debug: self.pluginHelper.indigo.server.log("Raw response: " + str(response))

				json_ustr = simplejson.dumps(response, ensure_ascii=False )
				convertedResponse = json_ustr.encode('utf-8')

				if self.pluginHelper.debug: 
					self.pluginHelper.indigo.server.log("Decoded response: " + str(convertedResponse))

				responseMessage = simplejson.loads(convertedResponse)
				subscription = responseMessage["ConfirmSubscriptionResponse"]["ConfirmSubscriptionResult"]["SubscriptionArn"]

				if self.pluginHelper.debug: 
					self.pluginHelper.indigo.server.log("JSON Subscription Token is: " + subscription)

				self.pluginHelper.confirmSubscription(topicArn, subscription)

				amSubscribed = self.pluginHelper.amSubscribed(topic)
				if self.pluginHelper.debug: 
					self.pluginHelper.indigo.server.log("isConfirmed status for : " + topicArn + " is now: " + str(amSubscribed))

			elif bodyJSON["Type"] == "Notification":
				topic = self.pluginHelper.getTopic(bodyJSON["TopicArn"])

				if topic == None:
					self.pluginHelper.indigo.server.log("Received a SNS Message for a topic I am not subscribed to.")
					return

				if self.pluginHelper.debug: 
					self.pluginHelper.indigo.server.log("Received a SNS Message for topic: " + topicArn)
					self.pluginHelper.indigo.server.log("Processing a Notification, message: " + bodyJSON["Message"])

#				messageBodyJSON = simplejson.loads(str(bodyJSON["Message"]))
				messageBodyJSON = simplejson.loads(bodyJSON["Message"].encode('utf-8').strip())

				self.pluginHelper.mergeTopicKeys(topic, messageBodyJSON)
				self.pluginHelper.updateSNSDeviceState(topic, messageBodyJSON)

			elif self.pluginHelper.debug:
				self.pluginHelper.indigo.server.log("Ignoring Message, headers: ")
				self.pluginHelper.indigo.server.log(str(self.headers))
				self.pluginHelper.indigo.server.log("body: ")
				self.pluginHelper.indigo.server.log(str(body))
		except:
			self.pluginHelper.indigo.server.log("Error while processing a Message: ")
			self.pluginHelper.indigo.server.log(str(sys.exc_info()[0]))
			self.pluginHelper.indigo.server.log(str(traceback.format_exc()))
			self.pluginHelper.bucket.put(sys.exc_info())


