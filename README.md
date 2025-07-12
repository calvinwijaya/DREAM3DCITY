<img src="https://github.com/user-attachments/assets/1ef821a9-8308-40f9-abd1-6558ce49e1ab" width="600">

# DREAM-3D CITY

DREAM 3D City stands for **Digital Reconstruction, Editing, and Modeling 3D City** is an interactive GUI created by Geo-AI & HD Research Team, Department of Geodetic Engineering, Faculty of Engineering, Universitas Gadjah Mada. The application provides a simple and interactive way to reconstruct, select, and create 3D model. 

## Motivation
DREAM 3D City is motivated by the need to refine and repair the constructed 3D city from automatic reconstruction algorithm. Various automatic 3D city reconstruction algorithm sometimes not giving the best result or the representative building. Hence, there is a need to refine the bad quality building. DREAM 3D allows user to load CityJSON files and select interactively which building that are needed to repair, exported it in OBJ format for manual refinement then convert it back to CityJSON to merge again with the original file. The presentation of DREAM 3D City can be accessed in material below:

### [DREAM3D presentation](https://docs.google.com/presentation/d/e/2PACX-1vRkkwH2L_vFDhvxh-IlnvOrL3R941e-zA8sOvFDS5g3T4jJDTBYartOxJCEkIeF5NHW-yPlXEVOfhj8/pub?start=false&loop=false&delayms=3000)

## Prerequisites & Instalations
The GUI was built in Windows environment, using PyQt6 library. To use DREAM 3D ensure you have a Conda or Miniconda installed. To build the application, please follow steps below:
1. Clone or download this repo.
2. Open Anaconda or Miniconda prompt. Find the conda path:
   ```
   where conda
   ```
3. Copy the path to conda.bat to **dream3d.bat** at
   ```
   "CONDA_PATH=...\conda.bat".
   ```
4. Close the bat, then click twice on **dream3d.bat**, it will automatically create a venv called dream3d.
5. After venv created, close the prompt, then run the **dream3d.bat** again to install all requirements needed.
6. Next, just click twice **dream3d.bat** to open DREAM 3D. It will skip the venv creation and library needed if previously has been installed

### Note:
For complete and fully functional DREAM 3D, we recommend to also install several library below:
- [Geoflow](https://github.com/geoflow3d/geoflow-bundle). We do not own the algorithm, please [cite Geoflow](https://github.com/geoflow3d/geoflow-bundle/blob/master/CITATION.bib) properly if using the first tab of DREAM 3D.
- [Go](https://go.dev/doc/install)

## How to use
DREAM 3D is a simple, user friendly, and very easy to use. It is GUI based where user can load and process data by pressing button. The functionalities of each tab is shown below:
1. **Tab 1 - 3D Reconstruction**
   
   This tab use to reconstruct 3D city automatically, semantic-ready, in LOD1.2, 1.3 and 2.2. It use Geoflow as backend processing. Hence, DREAM 3D only facilitates the GUI, but all the credits for the 3D reconstruction algorithm belongs to the [Geoflow](https://github.com/geoflow3d/geoflow-bundle). For more details about the algorithm, please refer to [this paper](https://arxiv.org/abs/2201.01191). The tab will takes input as Geoflow where user needs to determine:
   a. Building footprint (in Shapefile/ Shp or Geopackage/ gpkg). Ensure it has fid attribute
   b. Classified point cloud (in las or laz format). Ensure it has classified minimum to class 2 (ground) and 6 (building).
In this tab, user only need to browse the location of the data, and has flexibility in configuring the advance parameters. The output directory can be custom based on user. The result is 3D city model reconstructed in CityJSON format.

   <img width="600" alt="image" src="https://github.com/user-attachments/assets/9153531e-0a0d-448b-8134-ad29eb1c89e4" />
   
   Several sample of 3D reconstruction result:
   
   <img width="600" alt="image" src="https://github.com/user-attachments/assets/7fef9a78-b807-432f-b0f6-22967cce2e08" />

2. **Tab 2 - 3D Visualize**

   This tab is the core of DREAM 3D City. It serve as UI where user can load CityJSON (result from tab 1) and interactively select which buildings need to refined again. It can load multiple data such as CityJSON, point cloud (both ground and building point cloud), building outline (in GeoJSON format), and 3D model in OBJ. User can interactively load CityJSON or OBJ file where it can be selected (selected model will highlighted in yellow). Then, selected building will exported into an OBJ in specific LOD (user-defined). While the un-selected CityJSON will converted into CityJSON v2.0, upgrade it into latest version.

   <img width="600" alt="image" src="https://github.com/user-attachments/assets/420a46c4-92c8-4ae7-b52a-c1f01bf24f18" />

   The second tab also provides another tool such as Slicing box to quality control the 3D city model (CityJSON or OBJ) with the point cloud data. It also facilitates user with various view controls.

   <img width="600" alt="image" src="https://github.com/user-attachments/assets/0440a9c1-ac66-432d-ba98-9c0bd5343ca4" />
   
4. Tab 3 - OBJ Tools
5. Tab 4 - OBJ to 3D City.
6. Tab 5 - Merge CityJSON. This tab used to merge original cityJSON and reconstructed CityJSON from tab 4, where it created from refined building
