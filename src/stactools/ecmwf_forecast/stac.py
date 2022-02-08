from __future__ import annotations

import logging
import pathlib
import re
import datetime
import dataclasses

import pystac
from pystac import (
    CatalogType,
    Collection,
    Extent,
    Item,
    Provider,
    ProviderRole,
    SpatialExtent,
    TemporalExtent,
)

logger = logging.getLogger(__name__)

# for the summaries?
REFERENCE_TIMES = ["00", "06", "12", "18"]
STREAMS = ["oper", "enfo", "waef", "scda", "scwv", "mmsf"]
# maybe do steps as two Intervals? hour_steps, minute_steps?
STEPS = (
    [f"{i}h" for i in range(0, 144, 3)] +    
    [f"{i}h" for i in range(144, 361, 6)] +  # TODO: double check this endpoint, and below
    [f"{i}m" for i in range(1, 8)]
)
STEP_UNITS = ["h", "m"]
TYPES = ["fc", "ef", "ep", "tf"]
FORMATS = ["grib2", "bufr"]


xpr = re.compile(r"(?P<reference_datetime>\d{10})0000-(?P<step>\d+[h|m])-(?P<stream>\w+)-(?P<type>\w+).(?P<format>\w+)")


@dataclasses.dataclass
class Parts:
    reference_datetime: datetime.datetime
    stream: str
    step: str
    type: str
    format: str
    filename: str

    @classmethod
    def from_filename(cls, filename: str) -> "Parts":
        filename = pathlib.Path(filename).name
        m = xpr.match(filename)
        if not m:
            raise ValueError(filename)
        d = m.groupdict()
        d["reference_datetime"] = datetime.datetime.strptime(d["reference_datetime"], "%Y%m%d%H")
        d["filename"] = filename
        return cls(**d)

    @property
    def item_id(self) -> str:
        return "-".join(["ecmwf", self.reference_datetime.isoformat(timespec="hours"), self.stream, self.type])

    @property
    def offset(self) -> datetime.timedelta:
        v, u = self.step[:-1], self.step[-1]
        v = int(v)

        if u == "h":
            offset = datetime.timedelta(hours=v)
        else:
            offset = datetime.timedelta(minutes=v)
            
        return offset


def create_collection() -> Collection:
    """Create a STAC Collection

    This function includes logic to extract all relevant metadata from
    an asset describing the STAC collection and/or metadata coded into an
    accompanying constants.py file.

    See `Collection<https://pystac.readthedocs.io/en/latest/api.html#collection>`_.

    Returns:
        Collection: STAC Collection object
    """
    providers = [
        Provider(
            name="ECMWF",
            roles=[ProviderRole.PRODUCER],
            url="https://www.ecmwf.int/",
        )
    ]
    # TODO: Add "Attribution" from https://confluence.ecmwf.int/display/UDOC/ECMWF+Open+Data+-+Real+Time, either in
    # STAC metadata or description or both.
    links = [
        pystac.Link(rel=pystac.RelType.LICENSE, target="https://creativecommons.org/licenses/by/4.0/", media_type="text/html"),
        pystac.Link(rel="documentation", target="https://confluence.ecmwf.int/display/UDOC/ECMWF+Open+Data+-+Real+Time", media_type="text/html"),
    ]

    extent = Extent(
        SpatialExtent([[-180.0, 90.0, 180.0, -90.0]]),
        TemporalExtent([[None, None]]),
    )
    keywords = [
        "ECMWF",
        "forecast",
        "weather",
    ]

    collection = Collection(
        id="ecmwf-forecast",
        title="ECMWF Open Data (real-time)",
        description="description",
        license="CC-BY-4.0",
        providers=providers,
        extent=extent,
        catalog_type=CatalogType.RELATIVE_PUBLISHED,
        keywords=keywords,
    )
    collection.add_links(links)

    # Summaries
    collection.summaries.maxcount = 50
    summaries = {
        "ecmwf:reference_times": REFERENCE_TIMES,
        "ecmwf:streams": STREAMS,
        "ecmwf:steps": STEPS,
        "ecmwf:types": TYPES,
    }
    for k, v in summaries.items():
        collection.summaries.add(k, v)

    return collection


def item_key(filename) -> tuple[datetime.datetime, str, str]:
    parts = Parts.from_filename(filename)
    return parts.reference_datetime, parts.stream, parts.type


def create_item(asset_hrefs: list[str]) -> Item:
    parts = [Parts.from_filename(href) for href in asset_hrefs]
    part = parts[0]

    geometry = {
        "type": "Polygon",
        "coordinates": (
            (
                (180.0, -90.0),
                (180.0, 90.0),
                (-180.0, 90.0),
                (-180.0, -90.0),
                (180.0, -90.0),
            ),
        ),
    }
    bounds = (-180.0, -90.0, 180.0, 90.0)

    item = pystac.Item(
        part.item_id,
        geometry=geometry,
        bbox=bounds,
        datetime=part.reference_datetime,
        properties={},
    )
    offset = max(p.offset for p in parts)
    item.properties["start_datetime"] = part.reference_datetime.isoformat() + "Z"
    item.properties["end_datetime"] = (part.reference_datetime + offset).isoformat() + "Z"
    item.properties["ecmwf:stream"] = part.stream
    item.properties["ecmwf:type"] = part.type

    for href in asset_hrefs:
        p = Parts.from_filename(href)

        if p.format == "grib2":
            media_type = "application/wmo-GRIB2"
            roles = ["data"]
        elif p.format == "index":
            media_type = "application/x-ndjson"
            roles = ["index"]
        elif p.format == "bufr":
            media_type = None
            roles = ["data"]
        else:
            raise ValueError(f"Bad extension: {p.format}")

        item.add_asset(
            f"{p.step}-{p.format}",
            pystac.Asset(
                href,
                media_type=media_type,
                roles=roles,
                extra_fields={"ecmwf:step": p.step},
            ),
        )

    return item
