package main

import (
	"encoding/xml"
	"flag"
	"fmt"
	"io/ioutil"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

// XML namespaces and schema declarations
const (
	xmlHeader = `<?xml version="1.0" encoding="UTF-8"?>
<!-- Merged CityGML File -->
`
)

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

// OutputCityModel is the structure for the merged output with proper namespaces
type OutputCityModel struct {
	XMLName        xml.Name `xml:"core:CityModel"`
	GML            string   `xml:"xmlns:gml,attr"`
	Core           string   `xml:"xmlns:core,attr"`
	Bldg           string   `xml:"xmlns:bldg,attr"`
	App            string   `xml:"xmlns:app,attr"`
	Gen            string   `xml:"xmlns:gen,attr"`
	Grp            string   `xml:"xmlns:grp,attr"`
	XLink          string   `xml:"xmlns:xlink,attr"`
	XSI            string   `xml:"xmlns:xsi,attr"`
	SchemaLocation string   `xml:"xsi:schemaLocation,attr"`

	BoundedBy        OutputBoundedBy          `xml:"gml:boundedBy"`
	CityObjectMember []OutputCityObjectMember `xml:"core:cityObjectMember"`
}

type OutputBoundedBy struct {
	Envelope OutputEnvelope `xml:"gml:Envelope"`
}

type OutputEnvelope struct {
	SrsName      string `xml:"srsName,attr"`
	SrsDimension string `xml:"srsDimension,attr,omitempty"`
	LowerCorner  string `xml:"gml:lowerCorner"`
	UpperCorner  string `xml:"gml:upperCorner"`
}

type OutputCityObjectMember struct {
	Building OutputBuilding `xml:"bldg:Building"`
}

type OutputBuilding struct {
	ID                 string               `xml:"gml:id,attr"`
	Function           string               `xml:"bldg:function,omitempty"`
	YearOfConstruction string               `xml:"bldg:yearOfConstruction,omitempty"`
	RoofType           string               `xml:"bldg:roofType,omitempty"`
	MeasuredHeight     OutputMeasuredHeight `xml:"bldg:measuredHeight,omitempty"`
	Lod1Solid          OutputLod1Solid      `xml:"bldg:lod1Solid"`
}

type OutputMeasuredHeight struct {
	Value string `xml:",chardata"`
	UOM   string `xml:"uom,attr"`
}

type OutputLod1Solid struct {
	Solid OutputSolid `xml:"gml:Solid"`
}

type OutputSolid struct {
	ID       string         `xml:"gml:id,attr"`
	Exterior OutputExterior `xml:"gml:exterior"`
}

type OutputExterior struct {
	CompositeSurface OutputCompositeSurface `xml:"gml:CompositeSurface"`
}

type OutputCompositeSurface struct {
	SurfaceMember []OutputSurfaceMember `xml:"gml:surfaceMember"`
}

type OutputSurfaceMember struct {
	Polygon OutputPolygon `xml:"gml:Polygon"`
}

type OutputPolygon struct {
	ID       string                `xml:"gml:id,attr"`
	Exterior OutputPolygonExterior `xml:"gml:exterior"`
}

type OutputPolygonExterior struct {
	LinearRing OutputLinearRing `xml:"gml:LinearRing"`
}

type OutputLinearRing struct {
	PosList string `xml:"gml:posList"`
}

// Function to parse coordinates from string
func parseCoordinates(coordStr string) (float64, float64, float64, error) {
	var x, y, z float64
	_, err := fmt.Sscanf(coordStr, "%f %f %f", &x, &y, &z)
	if err != nil {
		// Try alternative format
		parts := strings.Fields(coordStr)
		if len(parts) >= 3 {
			x, _ = strconv.ParseFloat(parts[0], 64)
			y, _ = strconv.ParseFloat(parts[1], 64)
			z, _ = strconv.ParseFloat(parts[2], 64)
			return x, y, z, nil
		}
		return 0, 0, 0, err
	}
	return x, y, z, nil
}

// Main function
func main() {
	// Parse command-line arguments
	inputDir := flag.String("input", "", "Directory containing CityGML files")
	outputFile := flag.String("output", "", "Output merged CityGML file")
	epsgCode := flag.String("epsg", "32748", "EPSG code for the coordinate reference system")
	flag.Parse()

	if *inputDir == "" || *outputFile == "" {
		fmt.Println("Usage: citygml-merger -input <input_directory> -output <output_file> [-epsg <epsg_code>]")
		return
	}

	// Find all GML files in the input directory
	gmlFiles, err := filepath.Glob(filepath.Join(*inputDir, "*.gml"))
	if err != nil {
		fmt.Printf("Error finding GML files: %v\n", err)
		return
	}

	// Add XML files as well (some CityGML files might have .xml extension)
	xmlFiles, err := filepath.Glob(filepath.Join(*inputDir, "*.xml"))
	if err == nil {
		gmlFiles = append(gmlFiles, xmlFiles...)
	}

	fmt.Printf("Found %d CityGML files to merge\n", len(gmlFiles))
	if len(gmlFiles) == 0 {
		fmt.Println("No files to merge. Exiting.")
		return
	}

	// Create output CityGML model with proper namespaces
	outputModel := OutputCityModel{
		GML:            "http://www.opengis.net/gml",
		Core:           "http://www.opengis.net/citygml/2.0",
		Bldg:           "http://www.opengis.net/citygml/building/2.0",
		App:            "http://www.opengis.net/citygml/appearance/2.0",
		Gen:            "http://www.opengis.net/citygml/generics/2.0",
		Grp:            "http://www.opengis.net/citygml/cityobjectgroup/2.0",
		XLink:          "http://www.w3.org/1999/xlink",
		XSI:            "http://www.w3.org/2001/XMLSchema-instance",
		SchemaLocation: "http://www.opengis.net/citygml/2.0 http://schemas.opengis.net/citygml/2.0/cityGMLBase.xsd http://www.opengis.net/citygml/building/2.0 http://schemas.opengis.net/citygml/building/2.0/building.xsd",
		BoundedBy: OutputBoundedBy{
			Envelope: OutputEnvelope{
				SrsName:      fmt.Sprintf("http://www.opengis.net/def/crs/EPSG/0/%s", *epsgCode),
				SrsDimension: "3",
				// We'll calculate these values as we process files
				LowerCorner: "0 0 0",
				UpperCorner: "0 0 0",
			},
		},
	}

	// Track bounding box for all models
	minX, minY, minZ := float64(999999), float64(999999), float64(999999)
	maxX, maxY, maxZ := float64(-999999), float64(-999999), float64(-999999)

	// Process each CityGML file
	successCount := 0
	errorFiles := []string{}

	for _, gmlFile := range gmlFiles {
		fmt.Printf("Processing %s...\n", filepath.Base(gmlFile))

		// Read file content
		fileContent, err := ioutil.ReadFile(gmlFile)
		if err != nil {
			fmt.Printf("Error reading file %s: %v\n", filepath.Base(gmlFile), err)
			errorFiles = append(errorFiles, filepath.Base(gmlFile))
			continue
		}

		// Preprocess the XML to handle namespace issues
		fileContentStr := string(fileContent)

		// Remove namespace prefixes from elements for flexible parsing
		// This is a simplistic approach - a more robust solution would use a proper XML parser
		fileContentStr = regexp.MustCompile(`<(/?)(gml|core|bldg):([^>\s]+)`).ReplaceAllString(fileContentStr, "<$1$3")

		// Parse CityGML file with relaxed namespace requirements
		var cityModel CityModel
		err = xml.Unmarshal([]byte(fileContentStr), &cityModel)
		if err != nil {
			fmt.Printf("Error parsing CityGML file %s: %v\n", filepath.Base(gmlFile), err)
			errorFiles = append(errorFiles, filepath.Base(gmlFile))
			continue
		}

		// Extract bounding box if available
		if cityModel.BoundedBy != nil && cityModel.BoundedBy.Envelope != nil {
			if cityModel.BoundedBy.Envelope.LowerCorner != "" && cityModel.BoundedBy.Envelope.UpperCorner != "" {
				// Parse lower corner
				lx, ly, lz, err := parseCoordinates(cityModel.BoundedBy.Envelope.LowerCorner)
				if err == nil {
					// Parse upper corner
					ux, uy, uz, err := parseCoordinates(cityModel.BoundedBy.Envelope.UpperCorner)
					if err == nil {
						// Update global bounding box
						if lx < minX {
							minX = lx
						}
						if ly < minY {
							minY = ly
						}
						if lz < minZ {
							minZ = lz
						}
						if ux > maxX {
							maxX = ux
						}
						if uy > maxY {
							maxY = uy
						}
						if uz > maxZ {
							maxZ = uz
						}
					}
				}
			}
		}

		// Convert to output model format with proper namespaces
		fileBaseName := strings.TrimSuffix(filepath.Base(gmlFile), filepath.Ext(gmlFile))

		// Add city objects to merged model
		for _, cityObjectMember := range cityModel.CityObjectMember {
			if cityObjectMember.Building == nil || cityObjectMember.Building.Lod1Solid == nil ||
				cityObjectMember.Building.Lod1Solid.Solid == nil ||
				cityObjectMember.Building.Lod1Solid.Solid.Exterior == nil ||
				cityObjectMember.Building.Lod1Solid.Solid.Exterior.CompositeSurface == nil {
				fmt.Printf("Warning: Building in %s has incomplete structure, skipping\n", filepath.Base(gmlFile))
				continue
			}

			// Create output building with proper namespaces
			outputBuilding := OutputBuilding{
				ID:                 fmt.Sprintf("%s_%s", fileBaseName, cityObjectMember.Building.ID),
				YearOfConstruction: cityObjectMember.Building.YearOfConstruction,
				RoofType:           cityObjectMember.Building.RoofType,
				Lod1Solid: OutputLod1Solid{
					Solid: OutputSolid{
						ID: fmt.Sprintf("%s_%s", fileBaseName, cityObjectMember.Building.Lod1Solid.Solid.ID),
						Exterior: OutputExterior{
							CompositeSurface: OutputCompositeSurface{},
						},
					},
				},
			}

			// Copy measured height if available
			if cityObjectMember.Building.MeasuredHeight != nil {
				outputBuilding.MeasuredHeight = OutputMeasuredHeight{
					Value: cityObjectMember.Building.MeasuredHeight.Value,
					UOM:   cityObjectMember.Building.MeasuredHeight.UOM,
				}
			}

			// Copy surface members with proper namespaces
			for _, surfaceMember := range cityObjectMember.Building.Lod1Solid.Solid.Exterior.CompositeSurface.SurfaceMember {
				if surfaceMember.Polygon == nil || surfaceMember.Polygon.Exterior == nil ||
					surfaceMember.Polygon.Exterior.LinearRing == nil {
					continue
				}

				outputSurfaceMember := OutputSurfaceMember{
					Polygon: OutputPolygon{
						ID: fmt.Sprintf("%s_%s", fileBaseName, surfaceMember.Polygon.ID),
						Exterior: OutputPolygonExterior{
							LinearRing: OutputLinearRing{
								PosList: surfaceMember.Polygon.Exterior.LinearRing.PosList,
							},
						},
					},
				}

				outputBuilding.Lod1Solid.Solid.Exterior.CompositeSurface.SurfaceMember = append(
					outputBuilding.Lod1Solid.Solid.Exterior.CompositeSurface.SurfaceMember, outputSurfaceMember)
			}

			// Add to output model
			outputModel.CityObjectMember = append(outputModel.CityObjectMember, OutputCityObjectMember{
				Building: outputBuilding,
			})
		}

		successCount++
	}

	// Update bounding box for merged model
	outputModel.BoundedBy.Envelope.LowerCorner = fmt.Sprintf("%f %f %f", minX, minY, minZ)
	outputModel.BoundedBy.Envelope.UpperCorner = fmt.Sprintf("%f %f %f", maxX, maxY, maxZ)

	// Generate XML
	output, err := xml.MarshalIndent(outputModel, "", "  ")
	if err != nil {
		fmt.Printf("Error generating merged XML: %v\n", err)
		return
	}

	// Add XML header
	xmlData := []byte(xmlHeader + string(output))

	// Write to output file
	if err := ioutil.WriteFile(*outputFile, xmlData, 0644); err != nil {
		fmt.Printf("Error writing output file: %v\n", err)
		return
	}

	// Print summary
	fmt.Printf("Successfully merged %d from %d CityGML files\n", successCount, len(gmlFiles))
	if len(errorFiles) > 0 {
		fmt.Printf("Failed to process %d files: %v\n", len(errorFiles), errorFiles)
	}
	fmt.Printf("Merged CityGML file written to: %s\n", *outputFile)
	fmt.Printf("Bounding box: [%s] to [%s]\n", outputModel.BoundedBy.Envelope.LowerCorner, outputModel.BoundedBy.Envelope.UpperCorner)
	fmt.Printf("Total buildings: %d\n", len(outputModel.CityObjectMember))
}

// // Helper function for string to float conversion
// func strconv.ParseFloat(s string, bitSize int) (float64, error) {
// 	// Implementation not shown - use the standard library
// 	return 0, nil
// }
