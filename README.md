Indigo SNS Client
===========================

Description
---
A plugin for Perceptive Automation's Indigo Home Automation Service (http://www.perceptiveautomation.com).  The plugin creates and manages virtual devices based on JSON and RDF objects that are recieved from Amazon's Simple Notification Service (SNS).

This plugin can be used out of the box, or as a development framework for bigger and better things.  See below for some example usage.

Example Usage
---
Say you could want Indigo to know a bit of data about your cellphone being on the network (for presence detection), and you have a message that is published from your DHCP server or using a network scanner like Fing (https://github.com/mlamoure/Fing-Device-Watch), and a message is published like so:

{
	"mac": "xx:xx:xx:xx:xx",
	"state": "onNetwork"
}

With this plugin, you could create a virtual device using the device templates I've created, and map your custom fields to the device template.  The plugin would then listen for updates for the "topic" (called an event), and reflect those changes in Indigo.  Triggers and Actions are fully supported based on the device states for the virtual devices I've created.  Another example, I've built a replacement to the existing Indigo FindMyiDevices plugin that Ben wrote (https://github.com/mlamoure/iCloudDeviceSNSPublisher.js) that publishes a message that looks like this:

{
    "deviceID": "LONG LONG STRING",
    "deviceName": "Michael's iPhone",
    "modelDisplayName": "iPhone",
    "batteryLevel": 1,
    "batteryStatus": "Charged",
    "LocationTimestamp": 1391963222620,
    "latitude": 38.00002,
    "longitude": -77.55554,
    "locationChanged": true
}

The phone device template can take some of these fields (Battery Level, Battery Status, Longitude, Latitude), and let you create a virtual device in Indigo.  The fields for your JSON message might be slightly different than mine, which you can map your fields to the device template.

Theory (the reason why I built this plugin)
---
One of the issues we see is that the home automation devices produce mesh networks that multiple subscribers can listen to.  This allows for infinite options where devices can speak to each other, but can also be centralized at a point like Indigo or your home automation hub of choice.  Often mesh networks are used in event-based architecture, where a message is sent when something of interest happens: e.g., a motion sensor is triggered.

With wifi or TCP devices, we have lots of flexibility to do something similar, and there are many ways to do so.  Unfortunately a lot of our Wifi home automation devices use the cloud in a proprietary way (http://www.perceptiveautomation.com/userforum/viewtopic.php?f=5&t=9752&sid=b2b59f1aaaccc634f2273d389adef057) or speak directly in a point-to-point way between devices, leading to a mess of communications.

I've chosen to use Amazon SNS in my household as a way to broadcast a message using event-based-architecture from a sensor or device and have multiple subscribers.  One of the benefits of this strategy is that I can have a subscriber that simply listens and records the data in a persistent store, for later use in analytics (https://github.com/mlamoure/Amazon-SNS-to-SPARQL-Logger).

Why Amazon SNS?  Enterprises have been doing message passing for years, but unfortunately most of us do not have a Enterprise Service Bus (the tool used for messaging in the enterprise),  nor do we want to take the time to set one up.  Amazon SNS is the intermediary for these messages, allowing for more than one subscriber to listen to a publisher's message.  See my potential users section below for a bit more theory on this.

Setup - Amazon Web Service and SNS
---
This will use YOUR account with Amazon Web Services, so it requires that you sign up for an account (http://aws.amazon.com).  You will have to give your billing information and attach a credit card.  The cost as of writing this README for using Amazon SNS is .60 per million messages.  Needless to say, I don't think you will rack up a high bill.

Security - This plugin DOES set up a HTTP server on your indigo machine using the port you specify.  The server will only process Amazon SNS messages and does not respond to HTTP GET.  It does not write to disk or execute anything, it simply parses JSON.

The plugin includes the libraries to perform auto port forwarding from your router.  I recommend you do this, rather than statically setting up port forwarding.  That way, when the plugin is turned off, so is the connection to the outside world.

When a message is published that the plugin is subscribed to, Amazon will connect to the plugin and pass the message.  As of right now, this is done over HTTP and NOT HTTPS.  The reason being, Amazon does not allow for self-signed certs, and they don't approve of the cheap SSL providers.  Therefore, be advised that the messages are coming in using clear text.  I'm working on a solution where you can self-encrypt the data on the publisher, then configure the indigo plugin to decrypt.  Anyone that wants to help with this, I'd greatly appreciate it.

Some specifics about Amazon SNS, including some information about security that might make you more comfortable: http://aws.amazon.com/sns/faqs/

Adding SNS Topics
---
The plugin "learns" the attributes of a JSON publisher once you add the topic.  Best practice is to add the topic and force a publication from the publisher to test out that you are receiving the messages BEFORE adding devices.  When you do this, the plugin learns the fields that have been found in your messages.  This makes creating a device much simpler, as you can select the fields from drop down lists rather than typing them manually and risking a mistake.

There is a checkbox option for SNS Topics to reset known properties (keys) upon the receipt of the next SNS Message (it's not immediate due to limitations of Indigo).  Use this if you have properties in your drop down that should not be published or used for a SNS Device.  This can e checked at any time, and once the next SNS message is received, the fields will be reset, and the flag will be unchecked.

Adding SNS Devices
---
See the SNS Topics before you begin to add devices.

Supported device "types":
	On/Off Device (fields: onState (NOTE: "off" is assumed when the state does not == the onState))
	Phone Device (fields: Longitude, Latitude, Battery Status, Battery Level)

A note about identifiers: The plugin supports looking for the "ID" of a virtual device in the body of the published message.  Additionally, the plugin supports the scenario where a message itself is the identifier, and no ID is present in the data.  In the latter case, you only want to create a single SNS Device for a topic, but I do not enforce this.

When creating a device, first make sure the plugin is configured properly and receiving messages.You will see messages being received in the console log, regardless of the debug status for the plugin.  Once you are in the add device screen, use the refresh button to repopulate the fields with any fields that have been learned.  You must select a topic before doing this.  As a last resort, specify the fields manually using the override options.  Note: When manually specifying fields, do not use quotes.  For JSON topics, do not use colons ":".  For RDF topics (not yet supported), use the FULL URI for the predicate, surrounded by angle brackets.  For both fields and values, I have tried to be good about ignoring case, but being consistent might still be a good practice.

To-Do List
---
1. Validation of the configuration fields is an issue, I'll improve it later.  For now, don't make mistakes when adding topics or devices.

2. Adding RDF as a supported message type

3. Additional device types:
	Geo-Location device without the phone properties
	Numeric Device type (like a dimmer)

4. Maybe - add support for geo-fencing




