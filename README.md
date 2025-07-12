<img src="https://github.com/user-attachments/assets/1ef821a9-8308-40f9-abd1-6558ce49e1ab" width="600">

# DREAM-3D CITY

DREAM 3D City stands for **Digital Reconstruction, Editing, and Modeling 3D City** is an interactive GUI created by Geo-AI & HD Research Team, Department of Geodetic Engineering, Faculty of Engineering, Universitas Gadjah Mada. The application provides a simple and interactive way to reconstruct, select, and create 3D model. 

## Motivation
DREAM 3D City is motivated by the need to refine and repair the constructed 3D city from automatic reconstruction algorithm. Various automatic 3D city reconstruction algorithm sometimes not giving the best result or the representative building. Hence, there is a need to refine the bad quality building. DREAM 3D allows user to load CityJSON files and select interactively which building that are needed to repair, exported it in OBJ format for manual refinement then convert it back to CityJSON to merge again with the original file. The presentation of DREAM 3C can be accessed in material below:

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
1. Tab 1 - 3D Reconstruction. 
2. Tab 2 - 3D Visualize.
3. Tab 3 - OBJ Tools.
4. Tab 4 - OBJ to 3D City.
5. Tab 5 - Merge CityJSON. This tab used to merge original cityJSON and reconstructed CityJSON from tab 4, where it created from refined building
