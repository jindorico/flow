from threading import RLock

from jflow.core import dates
from jflow.core.dates import timedelta, qdatetodate, get_livedate
from jflow.core.rates import objects
from jflow.core.rates import cacheObject
from jflow.utils.decorators import threadSafe

from loader import histloader, shistloader
from period import periodParser

__all__ = ['vendorfieldid',
           'rateFactory',
           'idFactory',
           'compositeFactory',
           'compositeCodeFactory']



class vendorfieldid(object):
    '''
    Vendor Field Id object
    '''
    def __init__(self, id, vid, field, vendor_field, vendor, numeric = True):
        self.id           = id
        self.vid          = vid
        self.field        = field
        self.vendor       = vendor
        self.vendor_field = vendor_field
        self.numeric      = numeric
        
    def __repr__(self):
        return '%s - %s - %s' % (self.vid,self.field,self.vendor)
    
    def __str__(self):
        return self.__repr__()
    
    def code(self):
        try:
            return '%s:%s:%s' % (self.id.code,self.field.code,self.vendor.code)
        except:
            return ''
        
        
    
class novendorfieldid(vendorfieldid):
    
    def __init__(self, vid, field, vendor, numeric = True):
        super(novendorfieldid,self).__init__(None,vid,field,None,vendor,numeric)
        




class rateFactory(cacheObject):
    '''
    Base class for rate factories.
    A rateFactory is an utility class for creating rates.
    '''
    def __init__(self):
        self._history = None
        
    def __getstate__(self):
        odict = super(rateFactory,self).__getstate__()
        odict.pop('_history')
        return odict
        
    def __set_holder(self,h):
        self._history = h
    def __get_holder(self):
        return self._history
    holder = property(fget = __get_holder, fset = __set_holder)
    
    def __get_loaderpool(self):
        try:
            return self.cache.loaderpool
        except Exception, e:
            self.err('No loader pool')
    loaderpool = property(fget = __get_loaderpool)
    
    def populate(self):
        pass
    
    def __repr__(self):
        return self.code()
    
    def __str__(self):
        return self.code()
    
    def isproxy(self):
        return False
    
    def iscomposite(self):
        return isinstance(self,compositeFactory)
    
    def code(self):
        raise NotImplementedError

    def make(self, dte):
        raise NotImplementedError
    
    def get_fvid(self, field = None, vendor = None):
        raise NotImplementedError
    
    def loadhistory(self, start, end, field, vendor = None, period = None, parent = None):
        '''
        load historical data into cache.
        This function returns a twisted Deferred derived object
        to which the user can attach callbacks and errbacks
        '''
        el = periodParser.get(period or 'd',None)
        vid   = self.get_fvid(field,vendor)
        if vid:
            self.log("history request: %s to %s, %s" % (start,end,el.name), verbose = 3)
        else:
            self.err("no vendor field")
        return histloader(self, start, end, el, vid, parent = parent).load()
    
    def _loading_dates(self, start, end, vid):
        '''
        Select date range which needs to be fetch
        from cache or data provider
        '''
        if start > end:
            end = start
        
        realstart = start
        realend   = end
        
        if end.live:
            end = get_livedate(dates.prevbizday())
            
        _start = self.holder.start
        _end   = self.holder.end
        load = True
        if _start:
            oned = timedelta(days = 1)
            load = False
            if end > _end or start < _start:
                load = True
            
            if load:
                if end <= _end:
                    end = get_livedate(_start.date - oned)
                elif start >= _start:
                    start =  get_livedate(_end.date + oned)
                if start > end:
                    start = end
        
        return load, start, end, realstart, realend
    
    def _performload(self, start, end, field, vendor, handler=None):
        '''
        Called by histloader object
        '''
        pass
    
    def _handleresult(self, loader, res):
        return res
    
    def make_rate(self, code, dte):
        #
        # Invoke the cache
        cache = self.cache
        try:
            rateholder = cache.get_rate_holder(code)
            return rateholder.get_or_make(dte)
        except:
            return None
    
    

class idFactory(rateFactory):
    '''
        Rate factory for a Database Data ID
     id must have the following attributes/methods:
     
        get_field(field) (method)   return a string representing a valid field code
                                   
        code            (attribute) return a string representing the
                                    ASCII code of the data ID
                                    
        vendorid        (attribute) return an object which has
                                    the information about the data provider
    '''
    def __init__(self, id, ccy):
        super(idFactory,self).__init__()
        self.id     = id
        self.ccy    = ccy
        self.log("created", verbose = 4)
        self.hrates = None
        
    def __repr__(self):
        return self.code()
    
    def __str__(self):
        return '%s data id factory' % self.code()
    
    def code(self):
        return self.id.code
    
    def get_fvid(self, field = None, vendor = None):
        field = self.id.get_field(field)
        return self.id.vendorid(field, vendor)
    
    def make(self, dte):
        '''
        Create a new scalarrate
        '''
        ic = self.id.instrument()
            
        if self.ccy:
            return objects.ccyrate(id = self.id,
                                   ccy = self.ccy,
                                   holder = self.holder,
                                   dte = dte)
        else:
            return objects.scalarrate(id = self.id,
                                      holder = self.holder,
                                      dte = dte,
                                      inst = ic)       
        
    def _performload(self, loader, handler = None):
        '''
        Call the vendor interface to load time-series data
        '''
        vid = loader.vfid
        if vid:
            ci = vid.vendor.interface()
            if ci:
                self.log('loading "%s"' % vid, verbose = 3)
                return ci.history(vid,
                                  loader.start.date,
                                  loader.end.date,
                                  self.holder)
            else:
                self.err('Cannot load rate. Vendor "%s" has no interface available' % vid.vendor)
        else:
            self.err('Cannot load rate. No data vendor available')
    
    def populate(self):
        '''
        This function should populate the underlying factories
        '''
        pass
    

class compositeFactory(rateFactory):
    '''
    A composite rate factory.
    Implements the _performload method
    '''
    def __init__(self, numeric, *codes):
        super(compositeFactory,self).__init__()
        self.numeric     = numeric
        self.underlyings = list(codes)
        
    def __get_hrates(self):
        try:
            return getattr(self,'_hrates')
        except:
            hr = []
            for u in self.underlyings:
                rh = self.cache.get_rate_holder(u)
                hr.append(rh)
            self._hrates = hr
            return self._hrates
    hrates = property(fget = __get_hrates)
    
    def get_fvid(self, field = None, vendor = None):
        for hr in self.hrates:
            vid = hr.factory.get_fvid(field,vendor)
            return novendorfieldid(self.code(), vid.field, vid.vendor, self.numeric)
    
    def _handleresult(self, loader, res):
        self.log("received result from %s" % loader, verbose = 3)
        vfid = loader.vfid
        if res and vfid:
            nts    = self.holder.timeseries(vfid)
            hrates = self.hrates
            tseries = {}
            for rh,ts in res.values():
                tseries[rh.code] = ts
            self.buildcomposite(nts,tseries)
            
    def buildcomposite(self, cts, tseries):
        raise NotImplementedError
                
        



class compositeObjectFactory(compositeFactory):
    '''
    A composite object rate factory.
    '''
    def __init__(self, numeric, *codes):
        super(compositeObjectFactory,self).__init__(numeric, *codes)
    
    def _handleresult(self, loader, res):
        raise NotImplementedError
                    
                

class compositeCodeFactory(compositeObjectFactory):
    '''
    A composite rate factory.
    Implements the _performload method
    '''
    def __init__(self, code, numeric, *codes):
        self._code = code
        super(compositeCodeFactory,self).__init__(numeric, *codes)
        
    def code(self):
        return self._code
    
    
