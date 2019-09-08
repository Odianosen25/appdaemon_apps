import adbase as ad
import copy

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
        self.script_state_timer = None
        self.script_entity = f"script.{self.name.lower()}"
        service = f"script/{self.name.lower()}"

        self.adbase.run_in(self.register_script_services, 0, service=service)

        friendly_name = self.args.get("alias", self.name.replace("_", " ").title() + " Script")
        script_len = len(self.args["script"]) - 1
        self.adbase.set_state(self.script_entity, state="idle", friendly_name=friendly_name, index=0, lenght=script_len)

        #
        #Events
        #
        self.adbase.listen_event(self.process_entity, "script/run", entity_id=self.script_entity)
        self.adbase.listen_event(self.process_entity, "script/stop", entity_id=self.script_entity)
        self.adbase.listen_event(self.process_entity, "script/pause", entity_id=self.script_entity)
        self.adbase.listen_event(self.process_entity, "script/continue", entity_id=self.script_entity)
                
    def run_script(self):
        self.cancel_script() #incase it was running already
        self.continue_script()
        self.adbase.set_state(self.script_entity, state="running")

    def process_scripts(self, kwargs):
        script = self.args["script"]
        if not isinstance(script, list): #ensure it is a list
            script = [script]

        index = self.adbase.get_state(self.script_entity, attribute="index", copy=False, default=0) #start from beinging

        self.adbase.log("__function__: Running Script: {} and Index: {}".format(script, index), level="DEBUG")
        self.script_timer = None
        self.script_state_timer = None

        if (len(script) - 1) >= index:
            job = copy.deepcopy(script[index]) #pick the script
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
            
            elif "event" in job:
                event = job["event"]
                event_data = job["event_data"]
                self.adbase.fire_event(event, **event_data)

            elif "condition" in job:
                condition = job["condition"]
                conditions = job["conditions"]
                if condition == "state":
                    entity_id = conditions["entity_id"]
                    state = conditions["state"]
                    attribute = conditions.get("attribute", None)
                    namespace = conditions.get("namespace", "default")
                    if self.adbase.get_state(entity_id, attribute=attribute, copy=False, namespace=namespace) != state:
                        self.cancel_script() #just stop the script
                        return
            
            elif "wait" in job:
                wait_type = job["wait"]

                if wait_type == "state":
                    entity_id = job["entity_id"]
                    state = job["state"]
                    attribute = job.get("attribute", None)
                    namespace = job.get("namespace", "default")
                    self.script_state_timer = self.adbase.listen_state(self.wait_state_execute, entity_id, attribute=attribute, new=state, namespace=namespace, oneshot=True, immediate=True)
                    self.adbase.set_state(self.script_entity, index=index)
                    timeout = job.get("timeout", 0)

                    if timeout > 0:
                        self.script_timer = self.adbase.run_in(self.timed_out, timeout)
                return
            
            elif "repeat" in job:
                repeat = job.get("repeat", -1) #if == -1, continously run
                index = 0 #start all over

            self.adbase.set_state(self.script_entity, index=index)
            self.script_timer = self.adbase.run_in(self.process_scripts, delay)
        else:
            self.adbase.set_state(self.script_entity, state="idle", index=0)

    def wait_state_execute(self, entity, attribute, old, new, kwargs):
        if self.script_timer != None:
            self.adbase.cancel_timer(self.script_timer)

        self.continue_script() #continue script
        self.script_state_timer = None

    def timed_out(self, kwargs):
        if self.script_state_timer != None:
            self.adbase.cancel_listen_state(self.script_state_timer)

        self.continue_script() #continue script

    def cancel_script(self):
        self.adbase.log("__function__: Cancelling Script with Timer handle {}".format(self.script_timer), level = "DEBUG")
        self.pause_script()
        self.adbase.set_state(self.script_entity, state="idle", index=0)
    
    def pause_script(self):
        self.adbase.log("__function__: Pausing Script with Timer handle {}".format(self.script_timer), level = "DEBUG")

        if self.script_timer != None:
            self.adbase.cancel_timer(self.script_timer)
            self.script_timer = None

        if self.script_state_timer != None:
            self.adbase.cancel_listen_state(self.script_state_timer)
            self.script_state_timer = None
    
    def continue_script(self):
        index = self.adbase.get_state(self.script_entity, attribute="index", copy=False, default=0) #start from beinging
        self.adbase.log("__function__: Continuing Script from index {}".format(index), level = "DEBUG")
        self.script_timer = self.adbase.run_in(self.process_scripts, 0)

    def script_running(self):
        if self.script_timer == None and self.script_state_timer == None:
            return False
        else:
            return True

    def process_entity(self, event, data, kwargs):
        if event == "script/run":
            self.run_script()
        elif event == "script/stop":
            self.cancel_script()
        elif event =="script/pause":
            self.pause_script()
        elif event == "script/continue":
            self.continue_script()

    def register_script_services(self, kwargs):
        self.adbase.register_service(kwargs["service"], self.script_services)

    async def script_services(self, namespace, domain, service, kwargs):
        task = kwargs.get("task", None)

        if task == "run":
            await ad.utils.run_in_executor(self, self.run_script)
        
        elif task == "stop":
            await ad.utils.run_in_executor(self, self.cancel_script)
        
        elif task == "pause":
            await ad.utils.run_in_executor(self, self.pause_script)
        
        elif task == "continue":
            await ad.utils.run_in_executor(self, self.continue_script)

    def terminate(self):
        self.cancel_script()
