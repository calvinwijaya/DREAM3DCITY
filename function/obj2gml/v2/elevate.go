package main

import (
	"encoding/json"
	"encoding/xml"
	"flag"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

// GeoJSON structures
type GeoJSON struct {
	Type     string    `json:"type"`
	Features []Feature `json:"features"`
}

type Feature struct {
	Type       string     `json:"type"`
	Properties Properties `json:"properties"`
	Geometry   Geometry   `json:"geometry"`
}

type Properties struct {
	ID       string  `json:"id"`
	ELEVMean float64 `json:"ELEV_mean"`
}

type Geometry struct {
	Type        string      `json:"type"`
	Coordinates interface{} `json:"coordinates"`
}

// CityGML structures with flexible namespace handling
type CityModel struct {
	XMLName        xml.Name `xml:"CityModel"`
	GML            string   `xml:"xmlns:gml,attr,omitempty"`
	Core           string   `xml:"xmlns:core,attr,omitempty"`
	Bldg           string   `xml:"xmlns:bldg,attr,omitempty"`
	App            string   `xml:"xmlns:app,attr,omitempty"`
	Gen            string   `xml:"xmlns:gen,attr,omitempty"`
	Grp            string   `xml:"xmlns:grp,attr,omitempty"`
	XLink          string   `xml:"xmlns:xlink,attr,omitempty"`
	XSI            string   `xml:"xmlns:xsi,attr,omitempty"`
	SchemaLocation string   `xml:"xsi:schemaLocation,attr,omitempty"`

	BoundedBy        *BoundedBy         `xml:"boundedBy"`
	CityObjectMember []CityObjectMember `xml:"cityObjectMember"`
}

type BoundedBy struct {
	Envelope *Envelope `xml:"Envelope"`
}

type Envelope struct {
	SrsName      string `xml:"srsName,attr,omitempty"`
	SrsDimension string `xml:"srsDimension,attr,omitempty"`
	LowerCorner  string `xml:"lowerCorner"`
	UpperCorner  string `xml:"upperCorner"`
}

type CityObjectMember struct {
	Building *Building `xml:"Building"`
}

type Building struct {
	ID                 string          `xml:"id,attr,omitempty"`
	Function           string          `xml:"function,omitempty"`
	YearOfConstruction string          `xml:"yearOfConstruction,omitempty"`
	RoofType           string          `xml:"roofType,omitempty"`
	MeasuredHeight     *MeasuredHeight `xml:"measuredHeight,omitempty"`
	Lod1Solid          *Lod1Solid      `xml:"lod1Solid"`
}

type MeasuredHeight struct {
	Value string `xml:",chardata"`
	UOM   string `xml:"uom,attr,omitempty"`
}

type Lod1Solid struct {
	Solid *Solid `xml:"Solid"`
}

type Solid struct {
	ID       string    `xml:"id,attr,omitempty"`
	Exterior *Exterior `xml:"exterior"`
}

type Exterior struct {
	CompositeSurface *CompositeSurface `xml:"CompositeSurface"`
}

type CompositeSurface struct {
	SurfaceMember []SurfaceMember `xml:"surfaceMember"`
}

type SurfaceMember struct {
	Polygon *Polygon `xml:"Polygon"`
}

type Polygon struct {
	ID       string           `xml:"id,attr,omitempty"`
	Exterior *PolygonExterior `xml:"exterior"`
}

type PolygonExterior struct {
	LinearRing *LinearRing `xml:"LinearRing"`
}

type LinearRing struct {
	PosList string `xml:"posList"`
}

// Function to parse and adjust coordinates
func adjustCoordinates(coordStr string, elevationOffset float64) string {
	coords := strings.Fields(coordStr)
	adjustedCoords := make([]string, 0, len(coords))

	// Process coordinates in groups of 3 (x, y, z)
	for i := 0; i < len(coords); i += 3 {
		if i+2 < len(coords) {
			x := coords[i]
			y := coords[i+1]

			// Parse z coordinate and adjust it
			z, err := strconv.ParseFloat(coords[i+2], 64)
			if err != nil {
				// If parsing fails, keep original
				adjustedCoords = append(adjustedCoords, x, y, coords[i+2])
				continue
			}

			// Apply elevation offset
			adjustedZ := z + elevationOffset

			// Add adjusted coordinates to result
			adjustedCoords = append(adjustedCoords, x, y, fmt.Sprintf("%f", adjustedZ))
		} else {
			// Handle incomplete coordinate sets (shouldn't happen in valid GML)
			for j := i; j < len(coords); j++ {
				adjustedCoords = append(adjustedCoords, coords[j])
			}
		}
	}

	return strings.Join(adjustedCoords, " ")
}

// Function to adjust bounding box coordinates
func adjustBoundingBox(bbox string, elevationOffset float64) string {
	coords := strings.Fields(bbox)
	if len(coords) < 3 {
		return bbox // Not enough coordinates
	}

	// Parse z coordinate (assuming format is "x y z")
	z, err := strconv.ParseFloat(coords[2], 64)
	if err != nil {
		return bbox // Can't parse z
	}

	// Adjust z coordinate
	adjustedZ := z + elevationOffset

	// Return adjusted bounding box
	return fmt.Sprintf("%s %s %f", coords[0], coords[1], adjustedZ)
}

func main() {
	// Parse command-line arguments
	gmlDir := flag.String("gml", "", "Directory containing GML files")
	geojsonFile := flag.String("geojson", "", "GeoJSON file with elevation data")
	outputDir := flag.String("output", "", "Output directory for adjusted GML files")
	flag.Parse()

	if *gmlDir == "" || *geojsonFile == "" || *outputDir == "" {
		fmt.Println("Usage: gml-elevation-adjuster -gml <gml_directory> -geojson <geojson_file> -output <output_directory>")
		return
	}

	// Create output directory if it doesn't exist
	if err := os.MkdirAll(*outputDir, 0755); err != nil {
		fmt.Printf("Error creating output directory: %v\n", err)
		return
	}

	// Read and parse GeoJSON file
	geojsonData, err := ioutil.ReadFile(*geojsonFile)
	if err != nil {
		fmt.Printf("Error reading GeoJSON file: %v\n", err)
		return
	}

	var geojson GeoJSON
	if err := json.Unmarshal(geojsonData, &geojson); err != nil {
		fmt.Printf("Error parsing GeoJSON: %v\n", err)
		return
	}

	// Create a map of ID to elevation
	elevationMap := make(map[string]float64)
	for _, feature := range geojson.Features {
		elevationMap[feature.Properties.ID] = feature.Properties.ELEVMean
	}

	fmt.Printf("Loaded %d features with elevation data\n", len(elevationMap))

	// Process GML files
	gmlFiles, err := filepath.Glob(filepath.Join(*gmlDir, "*.gml"))
	if err != nil {
		fmt.Printf("Error finding GML files: %v\n", err)
		return
	}

	fmt.Printf("Found %d GML files to process\n", len(gmlFiles))

	processedCount := 0
	skippedCount := 0

	for _, gmlFile := range gmlFiles {
		// Extract ID from filename (assuming filename is ID.gml)
		baseFilename := filepath.Base(gmlFile)
		id := strings.TrimSuffix(baseFilename, filepath.Ext(baseFilename))

		// Find elevation for this ID
		elevation, found := elevationMap[id]
		if !found {
			fmt.Printf("Warning: No elevation data found for ID %s, skipping file\n", id)
			skippedCount++
			continue
		}

		// Read GML file
		fileContent, err := ioutil.ReadFile(gmlFile)
		if err != nil {
			fmt.Printf("Error reading file %s: %v\n", baseFilename, err)
			skippedCount++
			continue
		}

		// Preprocess the XML to handle namespace issues
		fileContentStr := string(fileContent)

		// Remove namespace prefixes from elements for flexible parsing
		fileContentStr = regexp.MustCompile(`<(/?)(gml|core|bldg):([^>\s]+)`).ReplaceAllString(fileContentStr, "<$1$3")

		// Parse GML file
		var cityModel CityModel
		err = xml.Unmarshal([]byte(fileContentStr), &cityModel)
		if err != nil {
			fmt.Printf("Error parsing GML file %s: %v\n", baseFilename, err)
			skippedCount++
			continue
		}

		// Adjust bounding box if present
		if cityModel.BoundedBy != nil && cityModel.BoundedBy.Envelope != nil {
			if cityModel.BoundedBy.Envelope.LowerCorner != "" {
				cityModel.BoundedBy.Envelope.LowerCorner = adjustBoundingBox(cityModel.BoundedBy.Envelope.LowerCorner, elevation)
			}
			if cityModel.BoundedBy.Envelope.UpperCorner != "" {
				cityModel.BoundedBy.Envelope.UpperCorner = adjustBoundingBox(cityModel.BoundedBy.Envelope.UpperCorner, elevation)
			}
		}

		// Process each building
		for i, cityObjectMember := range cityModel.CityObjectMember {
			if cityObjectMember.Building == nil || cityObjectMember.Building.Lod1Solid == nil ||
				cityObjectMember.Building.Lod1Solid.Solid == nil ||
				cityObjectMember.Building.Lod1Solid.Solid.Exterior == nil ||
				cityObjectMember.Building.Lod1Solid.Solid.Exterior.CompositeSurface == nil {
				continue
			}

			// Process each surface member
			for j, surfaceMember := range cityObjectMember.Building.Lod1Solid.Solid.Exterior.CompositeSurface.SurfaceMember {
				if surfaceMember.Polygon == nil || surfaceMember.Polygon.Exterior == nil ||
					surfaceMember.Polygon.Exterior.LinearRing == nil {
					continue
				}

				// Adjust coordinates
				posList := surfaceMember.Polygon.Exterior.LinearRing.PosList
				adjustedPosList := adjustCoordinates(posList, elevation)
				cityModel.CityObjectMember[i].Building.Lod1Solid.Solid.Exterior.CompositeSurface.SurfaceMember[j].Polygon.Exterior.LinearRing.PosList = adjustedPosList
			}
		}

		// Marshal adjusted GML
		output, err := xml.MarshalIndent(cityModel, "", "  ")
		if err != nil {
			fmt.Printf("Error generating adjusted XML for %s: %v\n", baseFilename, err)
			skippedCount++
			continue
		}

		// Add XML header
		xmlHeader := `<?xml version="1.0" encoding="UTF-8"?>
<!-- Elevation-adjusted CityGML -->
`
		xmlData := []byte(xmlHeader + string(output))

		// Write to output file
		outputFile := filepath.Join(*outputDir, baseFilename)
		if err := ioutil.WriteFile(outputFile, xmlData, 0644); err != nil {
			fmt.Printf("Error writing output file for %s: %v\n", baseFilename, err)
			skippedCount++
			continue
		}

		processedCount++

		// Print progress every 100 files
		if processedCount%100 == 0 {
			fmt.Printf("Processed %d files...\n", processedCount)
		}
	}

	// Print summary
	fmt.Printf("\nProcessing complete!\n")
	fmt.Printf("Successfully adjusted %d GML files\n", processedCount)
	fmt.Printf("Skipped %d GML files\n", skippedCount)
}
