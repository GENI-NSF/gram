
import datetime
import dateutil.parser

import config
import constants
import resources

class SliverList :
    """
        Some API calls return a list of slivers and information about
        the slivers.  This module helps create such lists.
    """
    def __init__(self) :
        self._sliver_list = []
    

    def addSliverStatus(self, sliver_object) :
        sliver_list_item = {}
        
        urn = sliver_object.getSliverURN()
        alloc_status = sliver_object.getAllocationState()
        expiration = sliver_object.getExpiration()
        oper_status = sliver_object.getOperationalState()
        expiration = sliver_object.getExpiration()
        
        if urn != None :
            sliver_list_item['geni_sliver_urn'] = urn
        if alloc_status != None :
            sliver_list_item['geni_allocation_status'] =  alloc_status
        if oper_status != None :
            sliver_list_item['geni_operational_status'] =  oper_status
        if expiration != None :
            sliver_list_item['geni_expires'] = _rfc3339format(expiration)
        sliver_list_item['geni_error'] = ''

        self._sliver_list.append(sliver_list_item)

    def getStatusAllSlivers(self, geni_slice) :
        """
            Return the status of all the slivers in the specified slice
        """
        vms = geni_slice.getVMs()
        for i in range(0, len(vms)) :
            self.addSliverStatus(vms[i])

        links = geni_slice.getNetworkLinks()
        for i in range(0, len(links)) :
            self.addSliverStatus(links[i])

        return self._sliver_list

    def getStatusOfSlivers(self, slivers) :
        """
            Return the status of the specified slivers
        """
        for sliver_object in slivers :
            self.addSliverStatus(sliver_object)

        return self._sliver_list
            

def min_expire(creds, max_duration=None, requested=None):
    """Compute the expiration time from the supplied credentials,
       a max duration, and an optional requested duration. The shortest
       time amongst all of these is the resulting expiration.
    """
    now = datetime.datetime.utcnow()
    expires = [_naiveUTC(c.expiration) for c in creds]
    if max_duration:
        expires.append(now + max_duration)
    if requested:
        requested = _naiveUTC(dateutil.parser.parse(str(requested)))
        # Ignore requested time in the past.
        if requested > now:
            expires.append(_naiveUTC(requested))

    return min(expires)


#########
### Private Support Functions
#########

def _naiveUTC(dt):
    """
        Converts dt to a naive datetime in UTC.
        if 'dt' has a timezone then 
            convert to UTC
            strip off timezone (make it "naive" in Python parlance)
    """
    if dt.tzinfo:
        tz_utc = dateutil.tz.tzutc()
        dt = dt.astimezone(tz_utc)
        dt = dt.replace(tzinfo=None)
    return dt


def _rfc3339format(dt):
        """
            Return a string representing the given datetime in rfc3339 format.
        """
        # Add UTC TZ, to have an RFC3339 compliant datetime, per the AM API
        # if 'dt' has a timezone then convert to UTC and strip off timezone 
        if dt.tzinfo :
            tz_utc = dateutil.tz.tzutc()
            dt = dt.astimezone(tz_utc)
            dt = dt.replace(tzinfo=None)
        time_with_tz = dt.replace(tzinfo=dateutil.tz.tzutc())
        return time_with_tz.isoformat()

