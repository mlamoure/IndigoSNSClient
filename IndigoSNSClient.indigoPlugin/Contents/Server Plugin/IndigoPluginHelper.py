import sys
import traceback
import urllib2
from xml.etree import ElementTree
from math import sin, cos, sqrt, atan2, radians
import time

class IndigoPluginHelper(object):
	debug = None
	snsEndpointURL = None
	s3Connection = None
	snsConnection = None
	indigo = None
	snsEndpointURL = None
	private_port = None
	public_port = None
	gatewayIP = None
	localEndpointURL = None
	topicSubscriptions = {}
	bucket = None

	def amSubscribed(self, topic):
		if topic == None:
			return False

		if isinstance(topic, basestring):
			topic = self.getTopic(topic)

		isConfirmed = False
		topicArn = topic.pluginProps["snsTopicArn"]

#		if self.debug: 
#			self.indigo.server.log("Checking the amSubscribed status for topic: " + topicArn)

		if topicArn in self.topicSubscriptions:
			if len(self.topicSubscriptions[topicArn]) > 0:
				isConfirmed = True

#		if self.debug: 
#			self.indigo.server.log("... is: " + str(isConfirmed))

		return isConfirmed

	def confirmSubscription(self, topicArn, subscription):
		if not isinstance(topicArn, basestring):
			topicArn = topicArn.pluginProps["snsTopicArn"]

		self.topicSubscriptions[topicArn] = subscription

		topic = self.getTopic(topicArn)
		topic.updateStateOnServer("status", value="confirmed")

	def getSubscription(self, topicArn):
		if not isinstance(topicArn, basestring):
			topicArn = topicArn.pluginProps["snsTopicArn"]

		if not topicArn in self.topicSubscriptions:
			return False

		return self.topicSubscriptions[topicArn]

	def clearSubscription(self, topicArn):
		if not isinstance(topicArn, basestring):
			topicArn = topicArn.pluginProps["snsTopicArn"]

		self.topicSubscriptions[topicArn] = ""

	def mergeTopicKeys(self, topic, data):
		topicArn = topic.pluginProps["snsTopicArn"]

		if topic.pluginProps["resetFields"] == True:
			self.indigo.server.log("Resetting all known fields for topic " + topicArn)
			self.replaceIndigoPluginProperty(topic, "knownKeys", [])
			self.replaceIndigoPluginProperty(topic, "resetFields", False)			

		if not "knownKeys" in topic.pluginProps:
			knownKeys = []
		else:
			knownKeys = topic.pluginProps["knownKeys"]

		for field in data:
			if not field in knownKeys:
				if len(str(field)) > 1 and not "," in field:
					self.indigo.server.log("Discovered a new key: " + field + " for topic: " + topicArn)
					knownKeys.append(field)
				else:
					if self.debug: self.indigo.server.log("New key not added (too short or illegal field): " + field + " for topic: " + topicArn)

		self.replaceIndigoPluginProperty(topic, "knownKeys", knownKeys)

	def updateSNSDeviceState(self, topic, deviceData):
		matchFound = False
		topicArn = topic.pluginProps["snsTopicArn"]
		messageTopicJSON = topic.pluginProps["messageFromat"] == "json"

		for device in self.getAllSNSTopicDevices(topic):
			# We only know what topic we are workig with, not the device, so we need to first discover that.
			if self.debug:
				self.indigo.server.log("Looking at device " + device.name + " as a potential match...")
			deviceIDField = self.getIndigoSNSDeviceIDField(device)
			deviceID = None
			deviceDataID = None

			if deviceIDField != None:
				if not deviceIDField in deviceData:
					if self.debug: self.indigo.server.log("Could not find the ID field (" + str(deviceIDField) + ") in the body of the message for topic " + topicArn)
					continue
				
				if self.debug:
					self.indigo.server.log("ID Field for device " + device.name + " was determined to be: " + deviceIDField)
				
				deviceDataID = deviceData[deviceIDField]
				deviceID = device.pluginProps["deviceIDValue"]

#			if self.debug:
#				self.indigo.server.log("Checking if " + device.deviceTypeId + " device: " + device.name + ", with ID:" + str(deviceID) + ", matches the message device ID of: "+ str(deviceDataID))

			# Now that we have the deviceID, or the device does not require a ID, we can proceed
			if deviceIDField == None or deviceDataID == deviceID:
				if device.deviceTypeId == "OnOffSNSDevice" or device.deviceTypeId == "NumericValueSNSDevice":
					if not device.pluginProps["deviceStateFieldOverride"]:
						stateField = device.pluginProps["deviceStateField"]
					else:
						stateField = device.pluginProps["deviceStateOverrideField"]

					if device.deviceTypeId == "OnOffSNSDevice":
						newValue = str(deviceData[stateField]).upper() == str(device.pluginProps["deviceStateOnValue"]).upper()
					elif device.deviceTypeId == "NumericValueSNSDevice":
						newValue = deviceData[stateField]

					device.updateStateOnServer("state", value=newValue)

					self.indigo.server.log(device.name + "[state]: " + str(newValue))

				elif device.deviceTypeId == "PhoneSNSDevice" or device.deviceTypeId == "LocationSNSDevice":
					if not device.pluginProps["deviceLocationFieldOverride"]:
						longitudeField = device.pluginProps["deviceLonField"]
						latitudeField = device.pluginProps["deviceLatField"]
						locationTimestampField = device.pluginProps["deviceLocationTimestampField"]

						if device.deviceTypeId == "PhoneSNSDevice":
							batteryStatusField = device.pluginProps["deviceBatteryStatusField"]
							batteryLevelField = device.pluginProps["deviceBatteryLevelField"]
					else:
						longitudeField = device.pluginProps["deviceLonOverrideField"]
						latitudeField = device.pluginProps["deviceLatOverrideField"]
						locationTimestampField = device.pluginProps["deviceLocationTimestampOverrideField"]

						if device.deviceTypeId == "PhoneSNSDevice":
							batteryStatusField = device.pluginProps["deviceBatteryStatusOverrideField"]
							batteryLevelField = device.pluginProps["deviceBatteryLevelOverrideField"]

					if messageTopicJSON:
						try:
							locationTimestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(deviceData[locationTimestampField]) / 1000))
						except Exception:
							try:
								locationTimestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(deviceData[locationTimestampField]))
							except Exception:
								locationTimestamp = "UNKNOWN"
								self.indigo.server.log("Could not set the location timestamp for " + device.name + ".")

					device.updateStateOnServer("locationTimestamp", value=str(locationTimestamp))
					device.updateStateOnServer("longitude", value=deviceData[longitudeField], decimalPlaces=6)
					device.updateStateOnServer("latitude", value=deviceData[latitudeField], decimalPlaces=6)

					if device.deviceTypeId == "PhoneSNSDevice":
						if deviceData[batteryStatusField].upper() != "UNKNOWN":
							device.updateStateOnServer("batteryStatus", value=deviceData[batteryStatusField])
							device.updateStateOnServer("batteryLevel", value=deviceData[batteryLevelField], decimalPlaces=2)

					self.indigo.server.log(device.name + "[longitude]: " + str(deviceData[longitudeField]))
					self.indigo.server.log(device.name + "[latitude]: " + str(deviceData[latitudeField]))
					self.indigo.server.log(device.name + "[locationTimestamp]: " + str(locationTimestamp))
					self.indigo.server.log(device.name + "[nearest address]: " + str(device.states["nearestLocation"]))

					self.setNearestAddress(device)
					self.setDistanceFromKnownLocations(device)

					if device.deviceTypeId == "PhoneSNSDevice":
						self.indigo.server.log(device.name + "[battery status]: " + deviceData[batteryStatusField])
						self.indigo.server.log(device.name + "[battery level]: " + str(deviceData[batteryLevelField]))

						if deviceData[batteryStatusField].upper() == "UNKNOWN":
							self.indigo.server.log(device.name + "[INFO]: Battery status and level ignored because they are unknown")

				matchFound = True
				break
			else:
				if self.debug: self.indigo.server.log(device.name + " did not match the device we are looking for")

		if not matchFound:
			if self.debug: 
				self.indigo.server.log("A match was not found for a SNS message to a Indigo SNS Device")

	def setDistanceFromKnownLocations(self, device):
		for location in self.getAllDeviceLocations(device):
			R = 6373.0

			lat1 = radians(float(device.states["latitude"]))
			lon1 = radians(float(device.states["longitude"]))
			lat2 = radians(float(location.pluginProps["latitude"]))
			lon2 = radians(float(location.pluginProps["longitude"]))

			dlon = lon2 - lon1
			dlat = lat2 - lat1
			a = (sin(dlat/2))**2 + cos(lat1) * cos(lat2) * (sin(dlon/2))**2
			c = 2 * atan2(sqrt(a), sqrt(1-a))
			distance = R * c

			self.indigo.server.log(location.name + "[distance]: " + str(round(distance, 3)) + " miles")
			location.updateStateOnServer("distance", value=distance, decimalPlaces=3)


	def setNearestAddress(self, device):
		lat = device.states["latitude"]
		lon = device.states["longitude"]
		newLocation = "unknown"
		validResult = False
		try:
			url = "http://maps.google.com/maps/api/geocode/xml?latlng=" + str(lat) + "," + str(lon) + "&sensor=false"
			
			response = urllib2.urlopen(url)
			the_page = response.read()

			tree = ElementTree.fromstring(the_page)

			if self.debug:
				self.indigo.server.log("Raw response from Google API: " + the_page)

			for child in tree.getiterator("status"):
				if child.text == "OK":
					validResult = True

			if validResult:
				for child in tree.getiterator("result"):
					if child[0].text == "street_address":
						newLocation = child[1].text
						break

			device.updateStateOnServer("nearestLocation", value=newLocation)
		except:
			device.updateStateOnServer("nearestLocation", value=newLocation)

	def replaceIndigoPluginProperty(self, device, replaceProperty, replaceValue):
		propsCopy = device.pluginProps

		if replaceValue == None:
			propsCopy[replaceProperty] = None
		else:
			propsCopy.update({replaceProperty:replaceValue})

		device.replacePluginPropsOnServer(propsCopy)


	def getTopic(self, topicArn):
		if not isinstance(topicArn, basestring):
			return

#		if self.debug: self.indigo.server.log("Looking for topic: " + topicArn)

		for indigoDevice in self.indigo.devices.iter("self.SNSTopic"):
			if indigoDevice.deviceTypeId == "SNSTopic":
				if indigoDevice.pluginProps["snsTopicArn"].upper() == topicArn.upper():
					return indigoDevice

		if self.debug: self.indigo.server.log("Device SNSTopic Device was not found for: " + topicArn)
		return None

	def isConfigured(self):
		return (self.snsConnection != None)


	def getAllSNSTopicDevices(self, topic):
		# need to handle if subscriptionTopic is the TopicArn or a indigo device
		if type(topic) is str:
			topic = getTopic(topic)

		topicArn = topic.pluginProps["snsTopicArn"]
		toReturn = []
		if self.debug: self.indigo.server.log("Looking up all SNS Devices for: " + topicArn)

		for indigoDevice in self.indigo.devices.iter("self"):
			if indigoDevice.deviceTypeId != "SNSTopic" and indigoDevice.id != 0 and "snsTopic" in indigoDevice.pluginProps:
				if int(indigoDevice.pluginProps["snsTopic"]) == topic.id:
					toReturn.append(indigoDevice)

		return toReturn

	def getAllDeviceLocations(self, device):
		toReturn = []
		for indigoDevice in self.indigo.devices.iter("self.location"):
			if indigoDevice.deviceTypeId == "location":
				if int(indigoDevice.pluginProps["snsDevice"]) == device.id:
					toReturn.append(indigoDevice)

		return toReturn

	def getAllSNSTopics(self):
		toReturn = []
		for indigoDevice in self.indigo.devices.iter("self.SNSTopic"):
			if indigoDevice.deviceTypeId == "SNSTopic":
				toReturn.append(indigoDevice)

		return toReturn

	def getIndigoSNSDeviceIDField(self, device):
		eventAsID = device.pluginProps["eventAsID"]
		deviceIDFieldOverride = device.pluginProps["deviceIDFieldOverride"]
		deviceIDField = device.pluginProps["deviceIDField"]
		deviceIDOverrideField = device.pluginProps["deviceIDOverrideField"]

		if eventAsID:
			return None
		elif deviceIDFieldOverride:
			return deviceIDOverrideField
		else:
			return deviceIDField
