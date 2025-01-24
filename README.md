# Project PTAL/Travel Time Lelylijn

This repository keeps track of the scripts used for our project about the Lelylijn, carried out under the instructions of KAW Groningen and the Rijksuniversiteit of Groningen.

## Overview

The project is divided into two main tasks:

### 1. Public Transport Accessibility Level (PTAL)
- **Baseline Calculation**: The PTAL score is first calculated as a baseline.
- **Scenarios**: PTAL is calculated for six different Lelylijn scenarios. 
- **Analysis**: In the final report, we analyze the results to determine which scenario shows the greatest improvement in the PTAL score.

### 2. Travel Time
- **Interactive Map**: An interactive map is created that allows users to click on a Service Access Point (SAP) (e.g., bus stops, train stops, etc.) to view isochrones. Isochrones illustrate how far you can travel in:
  - **30 minutes**
  - **1 hour**
- This is calculated both for the baseline and for the best scenario (based on the PTAL score).

---

## Data

### GTFS Data
- The GTFS data used in this project is sourced from [OVapi](https://gtfs.ovapi.nl/nl/).
- We used the `NL-20241203.gtfs.zip` file.
- **Note**: Due to the large size of the GTFS data files, they are not included in this repository. Instead, we have placed empty dummy files to show the required file structure and placement.

---

## Usage

1. Ensure the GTFS data (`NL-20241203.gtfs.zip`) is downloaded from [OVapi](https://gtfs.ovapi.nl/nl/) and placed in the appropriate folder as per the repository structure.
2. Follow the scripts and instructions provided in the report to calculate PTAL scores and generate travel time isochrones.

