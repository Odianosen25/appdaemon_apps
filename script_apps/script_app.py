import adbase as ad

class ScriptApp(ad.ADBase):
 
    def initialize(self): 
        self.adbase = self.get_ad_api() 
        self.script_timer = None
        self.script_state = None
                
    def run_script(self):
        self.cancel_script() #incase it was running already
        self.script_timer = self.adbase.run_in(self.process_scripts, 0)

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

            self.script_timer = self.adbase.run_in(self.process_scripts, delay, index=index)

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

    def script_running(self):
        if self.script_timer == None and self.script_state == None:
            return False
        else:
            return True