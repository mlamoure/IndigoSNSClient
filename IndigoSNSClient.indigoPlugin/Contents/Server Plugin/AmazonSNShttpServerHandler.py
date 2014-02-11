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
import sys
#import M2Crypto


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
			'''
# FIRST, VERIFY THE MESSAGE IS FROM AMAZON
# I've included Amazon's public key in the plugin, but it would be best to dynamically fetch this down the road.
			amazonPEM = """-----BEGIN CERTIFICATE-----
MIIFLTCCBBWgAwIBAgIQRXp96/v1XBAeRm45eB6eajANBgkqhkiG9w0BAQUFADCB
tTELMAkGA1UEBhMCVVMxFzAVBgNVBAoTDlZlcmlTaWduLCBJbmMuMR8wHQYDVQQL
ExZWZXJpU2lnbiBUcnVzdCBOZXR3b3JrMTswOQYDVQQLEzJUZXJtcyBvZiB1c2Ug
YXQgaHR0cHM6Ly93d3cudmVyaXNpZ24uY29tL3JwYSAoYykxMDEvMC0GA1UEAxMm
VmVyaVNpZ24gQ2xhc3MgMyBTZWN1cmUgU2VydmVyIENBIC0gRzMwHhcNMTMwOTEx
MDAwMDAwWhcNMTQwOTEyMjM1OTU5WjBqMQswCQYDVQQGEwJVUzETMBEGA1UECBMK
V2FzaGluZ3RvbjEQMA4GA1UEBxQHU2VhdHRsZTEYMBYGA1UEChQPQW1hem9uLmNv
bSBJbmMuMRowGAYDVQQDFBFzbnMuYW1hem9uYXdzLmNvbTCCASIwDQYJKoZIhvcN
AQEBBQADggEPADCCAQoCggEBAKpSGRs4IesnwfAABnP2vBxYAqwByHN4Ups5ylB3
kJUoJe2nJKJXkniLB6Jrczg9GDf5XSlmOKfRrQweFJjCnE7hnbL1AuYDrbsBzFlI
S8qN8RwNbCu1P9PwqQn2Q8ekwVh/kNaqACCOhkcBtUiXReCEnasWKFqnbj6zrlJs
zguD32O4vt7H5iE8eVtU42dc4J/2uzvEwQmn9W0lQcS/ucLeFlMYccNcU/oJxOap
Kg2auLatAzPm+gikUVnacUSwNHH4pnyCZ89cj9GZzu94WZFr+uohJu6gj28iVDIT
OoHzbsTsrAtLa8QWo1QmAFlU20wFFAetRWkUoQ/vTCSH4ZECAwEAAaOCAYEwggF9
MBwGA1UdEQQVMBOCEXNucy5hbWF6b25hd3MuY29tMAkGA1UdEwQCMAAwDgYDVR0P
AQH/BAQDAgWgMB0GA1UdJQQWMBQGCCsGAQUFBwMBBggrBgEFBQcDAjBDBgNVHSAE
PDA6MDgGCmCGSAGG+EUBBzYwKjAoBggrBgEFBQcCARYcaHR0cHM6Ly93d3cudmVy
aXNpZ24uY29tL2NwczAfBgNVHSMEGDAWgBQNRFwWU0TBgn4dIKsl9AFj2L55pTBF
BgNVHR8EPjA8MDqgOKA2hjRodHRwOi8vU1ZSU2VjdXJlLUczLWNybC52ZXJpc2ln
bi5jb20vU1ZSU2VjdXJlRzMuY3JsMHYGCCsGAQUFBwEBBGowaDAkBggrBgEFBQcw
AYYYaHR0cDovL29jc3AudmVyaXNpZ24uY29tMEAGCCsGAQUFBzAChjRodHRwOi8v
U1ZSU2VjdXJlLUczLWFpYS52ZXJpc2lnbi5jb20vU1ZSU2VjdXJlRzMuY2VyMA0G
CSqGSIb3DQEBBQUAA4IBAQARbCGQM7qTfF6jIfy0cenCUP7vx8+pSZqhBH+wrvHd
/JBIezBYI0iG8ufyTon9IAIg3YxLB3TgBxw9aOaerNhuJjKmNx5oQOdgbuxo9Iju
K/L3gkiWTd5jdpUrMHIHawQhyvXntgv7dDwHCbhgvnesrJzcuS/yM55tefmCzqgm
hAh/XKs1oqwFgaRvBUH8xFhMYSOOl6XDQrUE5WeFAOU0RO7sLjA4awE+8/W6nRAP
xzG/1Qvc1gHiE5ms+iWTa+Nd56MZkHpHRsfyydDv3Gp9Lsv86deEMzxNg8T4KuSJ
e3G8BZ+EAAIP8avZW1w6FPzklJp625XfNlavxSH086iA
-----END CERTIFICATE-----"""

			bio = BIO.MemoryBuffer(amazonPEM)
			rsa = RSA.load_pub_key_bio(bio)
			pubkey = EVP.PKey()
			pubkey.assign_rsa(rsa)

			# if you need a different digest than the default 'sha1':
			pubkey.reset_context(md='sha1')
			pubkey.verify_init()
			pubkey.verify_update(bodyJSON["Signature"])

			assert pubkey.verify_final(signature) == 1
			'''

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


