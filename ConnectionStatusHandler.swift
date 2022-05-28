//
//  ConnectionStatusHandler.swift
//  Smart Desk
//
//  Created by Alejandro Gomez
//  Copyright © 2020 ERGOCHIEF. All rights reserved.
//

import Foundation
import RealmSwift
        
class ConnectionStatusHandler{
    /* This handler has two parts:
     1. handleDeviceStatusMessage function: called by MQTT upon reception of a "DeviceStatus" message.
     -Detect Offline to Online events. Notify ".didChangeConnectionStatus"
     -Delete a device that does not exist in DB but exists in userDevicesCopy, when it tries to write event into real object.
     2.timer which selects (detectOfflineDevices):
     -Detect online to offline events:
      This checks for current devices status to judge if they are offline. Notify ".didChangeConnectionStatus".
     Offline detection will take at most (connectionTimeoutTime + timerInterval) seconds.
     -Add new user device: check if any new device and adds it to userDevicesCopy
    
     */
        
    static let shared = ConnectionStatusHandler()
    private let connectionTimeoutTime:Double = 60.0 //60 seconds
    private let realm = try! Realm()
    private var isSetup = false
    
    private var timer: Timer?
    private let timerInterval:Double = 20.0 //
    
    var userDevicesCopy: [IotDevice] = []
   
    func newTimer()->Timer{
        return Timer.scheduledTimer(
            timeInterval: self.timerInterval,
            target: self,
            selector: #selector(detectOfflineDevices),
            userInfo: nil,
            repeats: true
        )
    }
    func setupService() {
        timer = newTimer()
        
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(appWillResignActive),
            name: .UIApplicationWillResignActive,
            object: nil
        )
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(appDidBecomeActive),
            name: .UIApplicationDidBecomeActive,
            object: nil
        )

        self.userDevicesCopy = PeripheralManager.sharedInstance.peripheralsInDB!
        
        self.isSetup = true
    }

    
    @objc func appWillResignActive(){
        if self.timer != nil, isSetup{
            self.timer?.invalidate()
            self.timer = nil
        }
    }
    @objc func appDidBecomeActive(){
        if self.timer == nil, isSetup{
            self.timer = newTimer()
        }
    }
    @objc func loadNewUserDevices(){
        guard isSetup else {
            return
        }
        
        let newUserDevices = PeripheralManager.sharedInstance.peripheralsInDB!
        guard newUserDevices.count > 0 else {
            return
            }
        
        //add any new device to local copy
        for newUserDevice in newUserDevices {
            if let newSmartDesk = newUserDevice as? SmartDesk{
                
                //check if object exists in local copy
                 let objects = self.userDevicesCopy.filter { (device) -> Bool in
                    device.centralObjectId == newSmartDesk.centralObjectId
                }
                if objects.count < 1{
                    //add new device to local copy
                    self.userDevicesCopy.append(newUserDevice)
                }
            }
        }
    }
    
    
    func deleteLocalOutdatedDevice(_ device: IotDevice){
        //drop this local object
        if let index = self.userDevicesCopy.index(of: device){
            self.userDevicesCopy.remove(at: index)
        }
    }
    
    func handleDeviceStatusMessage(info: [String:Any]){
        if !(isSetup) {
            setupService()
        }
        
        let userDevices  =  self.userDevicesCopy
      
        guard userDevices.count > 0 else {
             self.userDevicesCopy = PeripheralManager.sharedInstance.peripheralsInDB!
            return
        }
        
        let time = info["time"] as? Double ?? 0.0
        let args = info["args"] as? [String: Any] ?? [:]
        let newLastAccesstime = Date(timeIntervalSince1970: time)
    
        
        let peripheralObjects = userDevices.filter { (device) -> Bool in
            device.centralObjectId == args["ObjectID"] as? Int ?? 0
        }
        
        if peripheralObjects.count > 0, let smartDesk = peripheralObjects[0] as? SmartDesk {
            
            let lastAccesstime = Date(timeIntervalSince1970: smartDesk.lastAccessTime)
            let isOffline = {return smartDesk.connectionStatus == 0 ? true : false}()
            let newStatusIsOnline = {return Date().timeIntervalSince(newLastAccesstime) < connectionTimeoutTime ? true: false}()
            
            //----Detect Offline to Online event-----:
            if isOffline, newStatusIsOnline{
                smartDesk.lastAccessTime =  time
                smartDesk.connectionStatus = 1 //online
                
                //Write online status to real realm object
                guard let realSmartDesk = PeripheralManager.sharedInstance.getOriginalPeripheralObject(withID: smartDesk.objectId) else {
                    return
                }
                
                if !(realSmartDesk.isInvalidated) {
                    try! self.realm.write{
                        
                        realSmartDesk.lastAccessTime = smartDesk.lastAccessTime
                        realSmartDesk.connectionStatus = smartDesk.connectionStatus
                        DispatchQueue.main.async {
                            NotificationCenter.default.post(name: .didChangeDeviceConnectionStatus, object: nil)
                        }
                    }
                }
            } else if !(isOffline), newStatusIsOnline {//Online to Online: update local time, not real db object.
                let isNewerStatusTime:Bool = Date().timeIntervalSince(newLastAccesstime) < Date().timeIntervalSince(lastAccesstime)
                if isNewerStatusTime{
                    smartDesk.lastAccessTime =  time
                }
            }
        }
        
    }
    
    @objc fileprivate func detectOfflineDevices() {
        //---------Detect Offline Events---------
        let userDevices = self.userDevicesCopy
        guard userDevices.count > 0 else {
                return
        }
        
        for device in userDevices {
            
            guard let smartDesk = device as? SmartDesk else {
                continue
            }
            
            let lastAccessTime = Date(timeIntervalSince1970: smartDesk.lastAccessTime)
            let isOffline = {return Date().timeIntervalSince(lastAccessTime) > connectionTimeoutTime ? true: false}()

            
            //Update from Online to Offline.
            if isOffline{
                smartDesk.connectionStatus = 0
                
                //Write offline status to real realm object
                guard let realSmartDesk = PeripheralManager.sharedInstance.getOriginalPeripheralObject(withID: smartDesk.objectId) else {

                self.deleteLocalOutdatedDevice(smartDesk)
                return
                }
                
                if !(realSmartDesk.isInvalidated),
                realSmartDesk.connectionStatus != 0 { //write to DB only if this is new offline event
                    try! self.realm.write {
//                        print("[ConnectionStatusHandler]: TIMER Writing to real object : offline event")
                        realSmartDesk.connectionStatus = 0
                    }
                    DispatchQueue.main.async {
                        NotificationCenter.default.post(name: .didChangeDeviceConnectionStatus, object: nil)
                    }
                }
            }
        }
        //---------Detect if any new device---------
        self.loadNewUserDevices()
    }
}
