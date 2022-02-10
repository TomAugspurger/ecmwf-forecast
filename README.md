# ecmwf-forecast

Create STAC metadata for [EMMWF Open Data - Real Time](https://confluence.ecmwf.int/display/UDOC/ECMWF+Open+Data+-+Real+Time).


## Planetary Computer collection


```console
stac ecmwf-forecast create-collection template.json \
    --thumbnail="https://ai4edatasetspublicassets.blob.core.windows.net/assets/pc_thumbnails/sentinel-2.png" \
    --extra-field "msft:short_description=ECMWF Open Data (Real Time) forecasts" \
    --extra-field "msft:storage_account=ai4edatauewest" \
    --extra-field "msft:container=ecmwf"
```
