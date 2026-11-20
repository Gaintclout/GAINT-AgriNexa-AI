"""Remote UTM parcel planning integration."""
from .scim_cog_utm_window import plan_projected_parcel_window

def plan_projected_grid(table, parcel, grid, margin_pixels=1):
    return plan_projected_parcel_window(table, parcel, transform=grid["transform"], crs=grid["crs"], margin_pixels=margin_pixels)
