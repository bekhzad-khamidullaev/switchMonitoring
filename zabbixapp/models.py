from django.db import models

class Host(models.Model):
    host_id = models.IntegerField(unique=True)
    host_name = models.CharField(max_length=255)

class Metric(models.Model):
    metric_id = models.IntegerField(unique=True)
    host = models.ForeignKey(Host, on_delete=models.CASCADE)
    metric_name = models.CharField(max_length=255)
    metric_value = models.FloatField()
