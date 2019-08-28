import adbase as ad

"""AppDaemon App For Writing HA like Script.
apps.yaml parameters:
| - service: Service to be called. 
| - service_data: The data to be used by the service call
| - delay: delay in seconds. This supports floats like 0.1
| - wait: This is still expanding, but for now, supports state wait. Whereby the script pauses until a state is true
| - repeat: This will repeat the previous tasks ran, and keep the script in a continous loop until stopped. USE WITH CAUTION
"""

"""
By using the script entity, for example script.living_room_kodi, other caps can be used to start,
check script running state, or stop the script if running

self.fire_event("script/run", entity_id="script.living_room_kodi", namespace="default"): used to run the script
self.fire_event("script/stop", entity_id="script.living_room_kodi", namespace="default"): used to stop a running script
self.get_state("script.living_room_kodi", namespace="default"): returns state of the script. "running" if busy and "idle" if not
"""

class ScriptApp(ad.ADBase):
 
    def initialize(self): 
        self.adbase = self.get_ad_api() 
        self.script_timer = None
        self.script_state = None
        self.script_entity = f"script.{self.name.lower()}"

        friendly_name = self.args.get("alias", self.name.replace("_", " ").title() + " Script")
        self.adbase.set_state(self.script_entity, state="idle", friendly_name=friendly_name)


        self.adbase.listen_event(self.process_entity, "script/run", entity_id=self.script_entity)
        self.adbase.listen_event(self.process_entity, "script/stop", entity_id=self.script_entity)
                
    def run_script(self):
        self.cancel_script() #incase it was running already
        self.script_timer = self.adbase.run_in(self.process_scripts, 0)
        self.adbase.set_state(self.script_entity, state="running")

    def process_scripts(self, kwargs):
        script = self.args["script"]
        if not isinstance(script, list): #ensure it is a list
            script = [script]

        index = kwargs.get("index", 0) #start from beinging

        self.adbase.log("__function__: Running Script: {} and Index: {}".format(script, index), level="DEBUG")
        self.script_timer = None

        if (len(script) - 1) >= index:
            job = script[index] #pick the script
            delay = 0
            index += 1 #increase it by 1
            if "service" in job:
                service = job["service"]
                service_data = job["service_data"]

                if service == "state/set":
                    entity_id = service_data["entity_id"]
                    del service_data["entity_id"]
                    self.adbase.set_state(entity_id, **service_data)
                else:
                    self.adbase.call_service(service, **service_data) 
            
            elif "delay" in job:
                delay = job["delay"]
            
            elif "log" in job:
                self.adbase.log(job["log"])
            
            elif "wait" in job:
                wait_type = job["wait"]

                if wait_type == "state":
                    entity_id = job["entity_id"]
                    state = job["state"]
                    attribute = job.get("attribute", None)
                    namespace = job["namespace"]
                    self.script_state = self.adbase.listen_state(self.wait_state_execute, entity_id, attribute=attribute, new=state, namespace=namespace, index=index, oneshot=True, immediate=True)
                return
            
            elif "repeat" in job:
                index = 0 #start all over

            self.script_timer = self.adbase.run_in(self.process_scripts, delay, index=index)
        else:
            self.adbase.set_state(self.script_entity, state="idle")

    def wait_state_execute(self, entity, attribute, old, new, kwargs):
        index = kwargs["index"]
        self.script_timer = self.adbase.run_in(self.process_scripts, 0, index=index) #continue script
        self.script_state = None

    def cancel_script(self):
        self.adbase.log("__function__: Cancelling Script with Timer handle {}".format(self.script_timer), level = "DEBUG")

        if self.script_timer != None:
            self.adbase.cancel_timer(self.script_timer)
            self.script_timer = None

        if self.script_state != None:
            self.adbase.cancel_listen_state(self.script_state)
            self.script_state = None
        
        self.adbase.set_state(self.script_entity, state="idle")

    def script_running(self):
        if self.script_timer == None and self.script_state == None:
            return False
        else:
            return True

    def process_entity(self, event, data, kwargs):
        if event == "script/run":
            self.run_script()
        elif event == "script/stop":
            self.cancel_script()

    def terminate(self):
        self.cancel_script()
