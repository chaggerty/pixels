# Databricks notebook source
# MAGIC %md ## Setup

# COMMAND ----------

token = dbutils.secrets.get("solution-accelerator-cicd", "github-pat")

# COMMAND ----------

# MAGIC %pip install git+https://token:$token@github.com/databricks-industry-solutions/pixels.git

# COMMAND ----------

# MAGIC %md ### Reload

# COMMAND ----------

# MAGIC %reload_ext autoreload
# MAGIC %autoreload 2

# COMMAND ----------

dbutils.widgets.text("path", "s3://hls-eng-data-public/dicom/ddsm/", label="1.0 Path to directory tree containing files. /dbfs or s3:// supported")
dbutils.widgets.text("table", "hive_metastore.pixels_solacc.object_catalog", label="2.0 Catalog Schema Table to store object metadata into")
dbutils.widgets.dropdown("mode",defaultValue="overwrite",choices=["overwrite","append"], label="3.0 Update mode on object metadata table")

path = dbutils.widgets.get("path")
table = dbutils.widgets.get("table")
write_mode = dbutils.widgets.get("mode")

spark.conf.set('c.table',table)
print(F"{path}, {table}, {write_mode}")

# COMMAND ----------

# MAGIC %md ## Test Plotting

# COMMAND ----------

from databricks.pixels import Catalog, DicomFrames
help(DicomFrames)

# COMMAND ----------

from databricks.pixels import Catalog, DicomFrames
catalog = Catalog(spark, path=path, table=table)
dcm_df_filtered = catalog.load().filter('meta:img_max < 1000').limit(100)

plots = DicomFrames(dcm_df_filtered, withMeta=True, inputCol="local_path").plot()
len(plots)

# COMMAND ----------

plots._files

# COMMAND ----------

from databricks.pixels import dicom_plot_udf
from pyspark.sql.functions import col

plot_df = (dcm_df_filtered.withColumn(
                'plot',
                dicom_plot_udf(col('local_path')))
)
display(plot_df)

# COMMAND ----------

plots._get_rows()

# COMMAND ----------

# MAGIC %md # Test Metadata extraction

# COMMAND ----------

from databricks.pixels import DicomMetaExtractor # The transformer
from databricks.pixels import Catalog, DicomFrames
catalog = Catalog(spark, path=path, table=table)

print(catalog.is_anon())
catalog_df = catalog.load()

# COMMAND ----------

meta = DicomMetaExtractor(catalog)
meta_df = meta.transform(catalog_df.filter('extension = "dcm"').repartition(1_000))
display(meta_df.select('meta'))

# COMMAND ----------

catalog.save(meta_df)

# COMMAND ----------

# MAGIC %md # Thumbnail dataframe

# COMMAND ----------

# load metata from the catalog

from databricks.pixels import Catalog
catalog = Catalog(spark, path=path, table=table)
dcm_df_filtered = catalog.load().filter('meta:img_max < 1000').repartition(1000).limit(10)
dcm_df_filtered.count()

# COMMAND ----------

from databricks.pixels import DicomThumbnailExtractor
help(DicomThumbnailExtractor)

# COMMAND ----------

from databricks.pixels import DicomThumbnailExtractor # The transformer
thumbnail_df = DicomThumbnailExtractor().transform(dcm_df_filtered)
display(thumbnail_df)

# COMMAND ----------

from pyspark.sql.functions import col
image_meta = {"spark.contentAnnotation" : '{"mimeType": "image/png"}'}

df = thumbnail_df.withColumn("content", col('thumbnail.data').alias("content",metadata=image_meta)).drop('thumbnail')

#image_meta = {"spark.contentAnnotation" : '{"mimeType": "image/jpeg"}'}
#df = df.withColumn("content", resize_image_udf(col("content")).alias("content", metadata=image_meta))
display(df.select('content'))

# COMMAND ----------

'/tmp/thumbnails'# images already compressed
spark.conf.set("spark.sql.parquet.compression.codec", "uncompressed") 

# add user defined metadata
meta = {'metadata':'1.2.3','batchId':2345, 'status':'initial','precision':1.5839}
spark.conf.set("spark.databricks.delta.commitInfo.userMetadata",str(meta))

# save all the images
thumbnail_df.write.format('delta').mode('overwrite').save('/tmp/thumbnails')

# COMMAND ----------


