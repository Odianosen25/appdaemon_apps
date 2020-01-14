import adbase as ad
import numpy as np
import imutils
import cv2
import traceback
import json
import os


class ObjectDetect(ad.ADBase):

    def initialize(self):
        self.adapi = self.get_ad_api()
        self.mqtt = self.get_plugin_api("MQTT")

        self._capturing = False
        self._object_detecting = None
        self._video_processing = None
        self._video_capture = None

        # setup to be ran in a thread, to avoid holding up AD
        self.adapi.run_in(self.setup_video_capture, 0)
    
    def setup_video_capture(self, kwargs):

        file_location = os.path.dirname(os.path.abspath(__file__))

        # load caffee object detection classes
        labelsPath = self.args.get("caffee_labels", f"{file_location}/caffee.names")
        
        # load object detection models
        object_prototxt = self.args.get("object_prototxt", f"{file_location}/MobileNetSSD_deploy.prototxt.txt")
        object_model = self.args.get("object_model", f"{file_location}/MobileNetSSD_deploy.caffemodel")
        self._camera_url = self.args.get("camera_url")
        self._topic = self.args.get("state_topic")

        if self._camera_url == None:
            raise ValueError ("Camera URL not provided")
        
        elif self._topic == None:
            raise ValueError ("State Topic not provided")

        try:
            # setup caffee object net
            self.caffee_object_net = cv2.dnn.readNetFromCaffe(object_prototxt, object_model)
            self.caffee_classes = open(labelsPath).read().strip().split("\n")

            # now setup capture
            # get capture
            self._video_capture = cv2.VideoCapture(self._camera_url)

            # get height and width
            height = self.args.get("height", 720)  
            width = self.args.get("width", 1280)

            # set height and width
            self._video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
            self._video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))

        except:
            self._video_capture.release()
            self._video_capture = None
            self.adapi.error(traceback.format_exc(), level="ERROR")
           
        if self._video_capture != None and self._video_capture.isOpened():
            # at this point, the video capture has been instanciated

            self._capturing = True
            # start processing
            self._object_detecting = self.adapi.create_task(self.process_detection())
    
    async def process_detection(self):
        self.adapi.log("Starting video processing and object detection")

        while self._capturing:
            try:
                # Check success
                if self._video_capture != None:
                    if not self._video_capture.isOpened():
                        raise Exception("Video device is not opened")

                    capture, frame = await self.adapi.run_in_executor(self._video_capture.read)

                    if capture:

                        detected_objects = await self.adapi.run_in_executor(self.detect_objects, frame)

                        await self.mqtt.mqtt_publish(self._topic, json.dumps(detected_objects))

                        await self.adapi.sleep(1)

            except:
                self.adapi.error("There was an error when processing image capture", level="ERROR")
                self.adapi.error(traceback.format_exc(), level="ERROR")
                await self.adapi.sleep(5)

    def detect_objects(self, image_data):
        minimum_confidence = self.args.get("minimum_confidence", 0.4)
        
        # generate random colours for each object
        colours = np.random.uniform(0, 255, size=(len(self.caffee_classes), 3))
        
        image_data = imutils.resize(image_data, width=400)

        try:
            (h, w) = image_data.shape[:2]
        except TypeError as t:
            self.adapi.error(t)
            return None

        blob = cv2.dnn.blobFromImage(cv2.resize(image_data, (300, 300)), 0.007843,
				(300, 300), 127.5)

        # pass the blob through the network and obtain the detections and
        # predictions
        self.caffee_object_net.setInput(blob)
        detections = self.caffee_object_net.forward()

        # loop over the detections
        number = 0
        objects_detected = {}

        # loop over the detections
        for i in np.arange(0, detections.shape[2]):
            # extract the confidence (i.e., probability) associated with
            # the prediction
            confidence = detections[0, 0, i, 2]
    
            # filter out weak detections by ensuring the `confidence` is
            # greater than the minimum confidence
            if confidence > minimum_confidence:
                # extract the index of the class label from the
                # `detections`, then compute the (x, y)-coordinates of
                # the bounding box for the object
                idx = int(detections[0, 0, i, 1])
                obj_class = self.caffee_classes[idx]

                if obj_class == "person":
                    obj_class = f"person_{number}"

                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    (startX, startY, endX, endY) = box.astype("int")
                    
                    obj_box = {}
                    obj_box["startX"] = int(startX)
                    obj_box["startY"] = int(startY)
                    obj_box["endX"] = int(endX)
                    obj_box["endY"] = int(endY)
                    obj_box["confidence"] = float(confidence)
                    objects_detected[obj_class] = obj_box
                    number +=1

        return objects_detected
    
    async def terminate(self):
        self.adapi.log("Stopping camera video capturing and detecting")

        if self._capturing is True:
            self._capturing = False

            await self.adapi.sleep(1)

        if self._object_detecting != None and (not self._object_detecting.done() or not self._object_detecting.cancelled()):
            self.adapi.log("Cancelling video processing and capturing")
            try:
                self._object_detecting.cancel()
            
            except asyncio.CancelledError:
                self.adapi.error("Cancelling video processing and capturing", level="DEBUG")
            
            self._object_detecting = None

        if self._video_capture != None: #first ensure the capture is closed
            self.adapi.log(f"Video Capture has been stopped. Releasing video capture now")
            await self.adapi.run_in_executor(self._video_capture.release)
            self._video_capture = None
            await self.adapi.sleep(1)