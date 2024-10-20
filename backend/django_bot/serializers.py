from rest_framework import serializers

class TradingParametersSerializer(serializers.Serializer):
    symbol = serializers.CharField(max_length=10)
    asset_a_funds = serializers.FloatField()
    asset_b_funds = serializers.FloatField()
    grids = serializers.IntegerField()
    deviation_threshold = serializers.FloatField()
    trail_price = serializers.BooleanField()
    only_profitable_trades = serializers.BooleanField()

