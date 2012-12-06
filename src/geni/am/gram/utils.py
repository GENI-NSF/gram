
import datetime
import dateutil.parser

import config
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
        expiration = sliver_object.getExpiration()
        # oper_status = sliver_object.getOperationalState()
        expiration = sliver_object.getExpiration()
        
        if urn != None :
            sliver_list_item['geni_sliver_urn'] = urn
        if alloc_status != None :
            sliver_list_item['geni_allocation_status'] =  alloc_status
        if expiration != None :
            sliver_list_item['geni_expires'] = rfc3339format(expiration)

        self._sliver_list.append(sliver_list_item)


    def getSliverStatusList(self) :
        return self._sliver_list


def rfc3339format(dt):
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


class ExpirationTimesSetter :
    """
        Base class for classes that set the expiration times on slivers.
        Expiration times are set on allocate, provision and renew.
    """
    max_alloc_time = \
        datetime.timedelta(minutes=config.allocation_expiration_minutes)
    max_prov_time = \
        datetime.timedelta(minutes=config.lease_expiration_minutes)

    def __init__(self, slice_obj, credentials, requested_time) :
        self._geni_slice = slice_obj    # Set times on slivers of this slice
        self._creds = credentials       # Experimenter slice credentials
        self._request = requested_time  # Experimenter requested expiration time
        self._expiration_time = None    # Expiration time for slivers
        
    def calculateExpirationTime(self, max_allowed_time) :
        """
            Compute the expiration time from the supplied credentials,
            max allowed time, and an optional requested duration. 
            Return the shortest of these times.
        """
        # For now we are ignoring slice expiration times and requested times
        now = datetime.datetime.utcnow()
        return now + max_allowed_time
        

        ### expires = [self._naiveUTC(c.expiration) for c in creds]
        ### if max_duration:
        ###     expires.append(now + max_duration)
        ### if requested:
        ##     requested = self._naiveUTC(dateutil.parser.parse(str(requested)))
        ###     # Ignore requested time in the past.
        ###     if requested > now:
        ###         expires.append(self._naiveUTC(requested))
        ### return min(expires)

    def setExpirationTime(self, sliver) :
        sliver.setExpiration(self._expiration_time)
        

class AllocationTimesSetter(ExpirationTimesSetter) :
    """
        Sets expiration times on slivers that don't already have one.
    """
    def __init__(self, slice_obj, credentials, requested_time = None) :
        ExpirationTimesSetter.__init__(self, slice_obj, credentials,
                                       requested_time)

        # Calculate the expiration time that will be set on the slivers
        self._expiration_time = \
            self.calculateExpirationTime(ExpirationTimesSetter.max_alloc_time)

        # Find the slivers that need their expiration times set
        all_slivers = self._geni_slice.getSlivers()
        for sliver_urn in all_slivers :
            sliver = all_slivers[sliver_urn]
            if sliver.getAllocationState() == config.allocated and \
                    sliver.getExpiration() == None :
                # This sliver has been allocated but does not have an
                # expiration time.  Set it.
                self.setExpirationTime(sliver)
            

class ProvisionTimesSetter(ExpirationTimesSetter) :
    """
        Sets expiration times on slivers that don't already have one.
    """
    def __init__(self, slice_obj, credentials, requested_time = None) :
        ExpirationTimesSetter.__init__(self, slice_obj, credentials,
                                       requested_time)

        # Calculate the expiration time that will be set on the slivers
        self._expiration_time = \
            self.calculateExpirationTime(ExpirationTimesSetter.max_prov_time)

        # Find the slivers that need their expiration times set
        all_slivers = self._geni_slice.getSlivers()
        for sliver_urn in all_slivers :
            sliver = all_slivers[sliver_urn]
            if sliver.getAllocationState() == config.provisioned :
                self.setExpirationTime(sliver)
