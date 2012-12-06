
import resources

class SliverList :
    """
        Some API calls return a list of slivers and information about
        the slivers.  This module helps create such lists.
    """
    def __init__(self) :
        self._sliver_list = []
    

    def addSliver(self, sliver_object) :
        sliver_list_item = {}
        
        urn = sliver_object.getSliverURN()
        alloc_status = sliver_object.getAllocationState()
        # oper_status = sliver_object.getOperationalState()
        # expiration = sliver_object.getExpiration()
        
        if urn != None :
            sliver_list_item['geni_sliver_urn'] = urn
        if alloc_status != None :
            sliver_list_item['geni_allocation_status'] =  alloc_status

        self._sliver_list.append(sliver_list_item)


    def getSliverStatusList(self) :
        return self._sliver_list
