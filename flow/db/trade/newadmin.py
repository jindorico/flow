from django.contrib import admin

from models import *
from jflow.db.trade.forms import TraderForm

#_______________________________________________________________ INLINES
#class PortfolioDisplayComponentInline(admin.TabularInline):
#    model = PortfolioDisplayComponent
#    extra = 5



#_______________________________________________________________ ADMINS
class FundHolderAdmin(admin.ModelAdmin):
    list_display = ('code','description','fund_manager')

class TraderAdmin(admin.ModelAdmin):
    list_display = ('user','fullname','is_active','is_staff','is_superuser','fund_holder','default_fund','default_history','machine','port','server_active')
    list_filter  = ('fund_holder',)
    #form = TraderForm

class FundAdmin(admin.ModelAdmin):
    list_display = ('code','firm_code', 'description','curncy','fund_holder','parent','dataid','type')
    list_filter  = ('fund_holder','type')
    
class CustodyAccountAdmin(admin.ModelAdmin):
    list_display = ('code','name','fund','dummy')
    list_filter  = ('fund',)

class PositionAdmin(admin.ModelAdmin):
    list_display  = ('dataid','fund','dt','status','size','value','dirty_value')
    list_filter   = ('status','fund',)
    ordering      = ('-dt',)
    search_fields = ('dataid__code',)

class UserViewDefaultAdmin(admin.ModelAdmin):
    list_display = ('user','view')


class ManualTradeAdmin(admin.ModelAdmin):
    list_display = ('dataid','user','open_date','close_date',
                    'fund','quantity','price')
    

admin.site.register(FundHolder,FundHolderAdmin)
admin.site.register(Trader,TraderAdmin)
admin.site.register(Fund,FundAdmin)
admin.site.register(CustodyAccount,CustodyAccountAdmin)
admin.site.register(Position,PositionAdmin)
admin.site.register(ManualTrade,ManualTradeAdmin)


