import adbase as ad
from datetime import timedelta, datetime

class Storage(ad.ADBase):
    def initialize(self):
        self.adbase = self.get_ad_api()
        self.adbase.set_namespace('storage')
        entityData = self.args.get('namespaces', {})
        allEntities = []

        for namespace, entities in entityData.items():
            if namespace == self.adbase._namespace:
                continue

            namespace = namespace.lower()
            allEntities.extend(entities)

            for entity in entities:
                if self.adbase.entity_exists(entity): #meaning it exists in this namespace so update the main one
                    entityState = self.adbase.get_state(entity, attribute = 'all')
                    entityState.update({'namespace' : namespace})
                    self.adbase.set_state(entity, **entityState) #create it in its needed namespace

                if not self.adbase.entity_exists(entity): #meaning it doesn't exist in this one
                    if self.adbase.entity_exists(entity, namespace = namespace): #meaning it exists in the other one
                        entityState = self.adbase.get_state(entity, attribute = 'all', namespace = namespace)
                        self.adbase.set_state(entity, **entityState) #create it in its needed namespace

                #self.adbase.listen_state(self.entity_changed, entity, eNamespace = namespace, namespace = namespace) #listen for state changes
                self.adbase.listen_event(self.entity_changed, "state_changed", entity_id = entity, namespace = namespace) #listen for state changes
        
        for entity in list(self.adbase.get_state().keys()):
            if entity not in allEntities and entity.split(".")[0] not in ["scheduler"] and "storage" in self.args["namespaces"] and entity not in self.args["namespaces"]["storage"]: #check if its one of the requested entity
                self.adbase.remove_entity(entity) # if not requested, then remove it
        
        time = datetime.now() + timedelta(seconds=1)
        self.adbase.run_every(self.save_lastest, time, 30 * 60) #save namespace every 30 minutes

    def entity_changed(self, event_name, data, kwargs):
        entityData = data["new_state"]
        entity_id = data["entity_id"]
        self.adbase.set_state(entity_id, **entityData, replace = True) #replicate in the storage namespace and replace

    def save_lastest(self, kwargs):
        self.adbase.save_namespace()