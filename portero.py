#!/usr/bin/env python
# -*- coding: utf-8 -*-

import linphone
import logging
import signal
import time
import daemon
import os
import sys
from gpiozero import Button
from gpiozero import LED
from gpiozero import DigitalOutputDevice
from signal import pause
import ConfigParser


class Portero:
  def __init__(self):
    self.quit = False    
    self.callRef = None
    self.callState = linphone.CallState.Idle
    self.registered = False   
    path = os.path.dirname(os.path.abspath(__file__))

    # configuration
    self.config = ConfigParser.ConfigParser() 
    self.configFilePath= path + '/config.rc'
    self.loadConfigFile(self.configFilePath)   
    
    self.ring_button_pin=self.config.getint("portero", "ring_button_pin")
    self.light_pin=self.config.getint("portero", "light_pin")
    self.door_lock_pin=self.config.getint("portero", "door_lock_pin")
    self.target_sip_account=self.config.get("portero", "target_sip_account")
    self.door_lock_open_time=self.config.getint("portero", "door_lock_open_time")


    # logging
    self.logger = logging.getLogger()
    self.logger.setLevel(logging.ERROR)
    self.logfile = logging.FileHandler(path + '/portero.log')
    self.logger.addHandler(self.logfile)
    
    # set linphone callbacks
    callbacks = linphone.Factory.get().create_core_cbs()
    callbacks.call_state_changed = self.call_state_changed
    callbacks.registration_state_changed = self.registration_state_changed
    callbacks.message_received = self.message_received
    linphone.set_log_handler(self.log_handler)

    self.quit_when_registered = False
    self.core = linphone.Factory.get().create_core(callbacks, path + '/config.rc', None)

    signal.signal(signal.SIGINT, self.signal_handler)
    self.path = path

    # configure hardware
    self.doorLock=DigitalOutputDevice(self.door_lock_pin)

    self.btn = Button(self.ring_button_pin, hold_time=0.5)
    self.btn.when_pressed = self.initCall
  
    self.lightOn()

  def loadConfigFile(self, configPath):    
    logging.info("Loading config from "+configPath)    
    self.config.read(configPath)

  def lightOn(self):
    self.led = LED(self.light_pin)
    self.led.on() 

  def lightOff(self):
    self.led = LED(self.light_pin)
    self.led.off() 

  def initCall(self):
    call = self.core.invite(self.target_sip_account)
   
    if call is None:
      print "outgoing call error"

  def signal_handler(self, signal, frame):
    self.core.terminate_all_calls()
    self.quit = True

  def log_handler(self, level, msg):
    method = getattr(logging, level)
    method(msg)

  def registration_state_changed(self, core, proxy, state, message):
    print "registration state changes"
    if self.quit_when_registered:
      if state == linphone.RegistrationState.Ok:
        print 'Account configuration OK'
        self.core.config.sync()
        self.quit = True
      elif state == linphone.RegistrationState.Failed:
        print 'Account configuration failure: {0}'.format(message)
        self.quit = True
    else:
      if state == linphone.RegistrationState.Ok:
        print "Registered OK"
        self.registered = True
        
 
  def call_state_changed(self, core, call, state, message):
    print "Estado cambiado a " + str(state)
    print "Message: " + message
    self.call=call
    self.callState=state
    if state == linphone.CallState.IncomingReceived:
      if call.remote_address.as_string_uri_only() == self.target_sip_account:
        params = core.create_call_params(call)
        core.accept_call_with_params(call, params)
      else:
        core.decline_call(call, linphone.Reason.Declined)
    elif state == linphone.CallState.OutgoingProgress:
      print "Call state changed to OutgoingProgress"
    elif state == linphone.CallState.OutgoingRinging:
      print "Call state changed to OutgoingRinging"
    elif state == linphone.CallState.Connected:
      print "Call state changed to Connected"
      chatRoom = core.get_chat_room_from_uri(call.remote_address.as_string_uri_only())
      msg = chatRoom.create_message("Connected from portero")
      chatRoom.send_chat_message(msg)

  def message_received(self, core, room, message):
    sender = message.from_address
    if sender.as_string_uri_only() == self.target_sip_account:
      
      if message.text=="open":      
        self.doorLock.blink(on_time=self.door_lock_open_time, n=1)

      msg = room.create_message("received " +message.text)
      room.send_chat_message(msg)
    
  def run(self):
    while not self.quit:
        self.core.iterate()
        
        if self.callState == linphone.CallState.Idle or self.callState == linphone.CallState.Released:
          self.btn.wait_for_press(timeout=1)

if __name__ == '__main__':
  portero = Portero()
  #context = daemon.DaemonContext(files_preserve = [ portero.logfile.stream, ],)
  #context.open()
  portero.run()
