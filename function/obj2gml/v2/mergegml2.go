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

// Output structures for CityGML LoD2
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

// OutputBuilding includes LoD2 solid and semantic surfaces
type OutputBuilding struct {
	ID             string                `xml:"gml:id,attr"`
	MeasuredHeight *OutputMeasuredHeight `xml:"bldg:measuredHeight,omitempty"`
	Lod2Solid      *OutputLod2Solid      `xml:"bldg:lod2Solid,omitempty"`
	BoundedBy      []SemanticSurface     `xml:"bldg:boundedBy,omitempty"`
}

type OutputMeasuredHeight struct {
	Value string `xml:",chardata"`
	UOM   string `xml:"uom,attr,omitempty"`
}

// LoD2 Solid
type OutputLod2Solid struct {
	Solid OutputSolid `xml:"gml:Solid"`
}
type OutputSolid struct {
	ID       string         `xml:"gml:id,attr,omitempty"`
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
	ID       string                `xml:"gml:id,attr,omitempty"`
	Exterior OutputPolygonExterior `xml:"gml:exterior"`
}
type OutputPolygonExterior struct {
	LinearRing OutputLinearRing `xml:"gml:LinearRing"`
}
type OutputLinearRing struct {
	PosList string `xml:"gml:posList"`
}

// LoD2 Semantic Surfaces (roof, wall, ground, etc.)
type SemanticSurface struct {
	XMLName          xml.Name          `xml:""`
	ID               string            `xml:"gml:id,attr,omitempty"`
	Lod2MultiSurface *Lod2MultiSurface `xml:"bldg:lod2MultiSurface,omitempty"`
}
type Lod2MultiSurface struct {
	MultiSurface MultiSurface `xml:"gml:MultiSurface"`
}
type MultiSurface struct {
	ID            string                `xml:"gml:id,attr,omitempty"`
	SurfaceMember []OutputSurfaceMember `xml:"gml:surfaceMember"`
}

// Parse coordinates helper
func parseCoordinates(coordStr string) (float64, float64, float64, error) {
	parts := strings.Fields(coordStr)
	if len(parts) >= 3 {
		x, _ := strconv.ParseFloat(parts[0], 64)
		y, _ := strconv.ParseFloat(parts[1], 64)
		z, _ := strconv.ParseFloat(parts[2], 64)
		return x, y, z, nil
	}
	return 0, 0, 0, fmt.Errorf("invalid coordinates")
}

// Main function
func main() {
	inputDir := flag.String("input", "", "Directory containing CityGML files")
	outputFile := flag.String("output", "", "Output merged CityGML file")
	epsgCode := flag.String("epsg", "32748", "EPSG code for the coordinate reference system")
	flag.Parse()

	if *inputDir == "" || *outputFile == "" {
		fmt.Println("Usage: citygml-merger -input <input_directory> -output <output_file> [-epsg <epsg_code>]")
		return
	}

	gmlFiles, _ := filepath.Glob(filepath.Join(*inputDir, "*.gml"))
	xmlFiles, _ := filepath.Glob(filepath.Join(*inputDir, "*.xml"))
	gmlFiles = append(gmlFiles, xmlFiles...)
	if len(gmlFiles) == 0 {
		fmt.Println("No files to merge. Exiting.")
		return
	}

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
				SrsName:      fmt.Sprintf("urn:ogc:def:crs:EPSG::%s", *epsgCode),
				SrsDimension: "3",
				LowerCorner:  "0 0 0",
				UpperCorner:  "0 0 0",
			},
		},
	}

	minX, minY, minZ := 1e20, 1e20, 1e20
	maxX, maxY, maxZ := -1e20, -1e20, -1e20

	for _, gmlFile := range gmlFiles {
		fileContent, err := ioutil.ReadFile(gmlFile)
		if err != nil {
			fmt.Printf("Error reading file %s: %v\n", gmlFile, err)
			continue
		}
		fileContentStr := string(fileContent)
		// Remove namespace prefixes for easier parsing
		fileContentStr = regexp.MustCompile(`<(/?)(gml|core|bldg|app):`).ReplaceAllString(fileContentStr, "<$1")
		type Building struct {
			XMLName        xml.Name `xml:"Building"`
			ID             string   `xml:"id,attr,omitempty"`
			MeasuredHeight *struct {
				Value string `xml:",chardata"`
				UOM   string `xml:"uom,attr,omitempty"`
			} `xml:"measuredHeight"`
			Lod2Solid *struct {
				Solid struct {
					ID       string `xml:"id,attr,omitempty"`
					Exterior struct {
						CompositeSurface struct {
							SurfaceMember []struct {
								Polygon struct {
									ID       string `xml:"id,attr,omitempty"`
									Exterior struct {
										LinearRing struct {
											PosList string `xml:"posList"`
										} `xml:"LinearRing"`
									} `xml:"exterior"`
								} `xml:"Polygon"`
							} `xml:"surfaceMember"`
						} `xml:"CompositeSurface"`
					} `xml:"exterior"`
				} `xml:"Solid"`
			} `xml:"lod2Solid"`
			BoundedBy []struct {
				XMLName          xml.Name `xml:""`
				ID               string   `xml:"id,attr,omitempty"`
				Lod2MultiSurface *struct {
					MultiSurface struct {
						ID            string `xml:"id,attr,omitempty"`
						SurfaceMember []struct {
							Polygon struct {
								ID       string `xml:"id,attr,omitempty"`
								Exterior struct {
									LinearRing struct {
										PosList string `xml:"posList"`
									} `xml:"LinearRing"`
								} `xml:"exterior"`
							} `xml:"Polygon"`
						} `xml:"surfaceMember"`
					} `xml:"MultiSurface"`
				} `xml:"lod2MultiSurface"`
			} `xml:"boundedBy"`
		}
		type CityObjectMember struct {
			Building Building `xml:"Building"`
		}
		type Envelope struct {
			SrsName      string `xml:"srsName,attr,omitempty"`
			SrsDimension string `xml:"srsDimension,attr,omitempty"`
			LowerCorner  string `xml:"lowerCorner"`
			UpperCorner  string `xml:"upperCorner"`
		}
		type BoundedBy struct {
			Envelope Envelope `xml:"Envelope"`
		}
		type CityModel struct {
			BoundedBy        BoundedBy          `xml:"boundedBy"`
			CityObjectMember []CityObjectMember `xml:"cityObjectMember"`
		}
		var cityModel CityModel
		if err := xml.Unmarshal([]byte(fileContentStr), &cityModel); err != nil {
			fmt.Printf("Error parsing file %s: %v\n", gmlFile, err)
			continue
		}
		// Update bounding box
		lx, ly, lz, _ := parseCoordinates(cityModel.BoundedBy.Envelope.LowerCorner)
		ux, uy, uz, _ := parseCoordinates(cityModel.BoundedBy.Envelope.UpperCorner)
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

		for _, com := range cityModel.CityObjectMember {
			b := com.Building
			outB := OutputBuilding{
				ID: b.ID,
			}
			if b.MeasuredHeight != nil {
				outB.MeasuredHeight = &OutputMeasuredHeight{
					Value: b.MeasuredHeight.Value,
					UOM:   b.MeasuredHeight.UOM,
				}
			}
			// lod2Solid
			if b.Lod2Solid != nil {
				outB.Lod2Solid = &OutputLod2Solid{
					Solid: OutputSolid{
						ID: b.Lod2Solid.Solid.ID,
						Exterior: OutputExterior{
							CompositeSurface: OutputCompositeSurface{},
						},
					},
				}
				for _, sm := range b.Lod2Solid.Solid.Exterior.CompositeSurface.SurfaceMember {
					outB.Lod2Solid.Solid.Exterior.CompositeSurface.SurfaceMember = append(
						outB.Lod2Solid.Solid.Exterior.CompositeSurface.SurfaceMember,
						OutputSurfaceMember{
							Polygon: OutputPolygon{
								ID: sm.Polygon.ID,
								Exterior: OutputPolygonExterior{
									LinearRing: OutputLinearRing{
										PosList: sm.Polygon.Exterior.LinearRing.PosList,
									},
								},
							},
						})
				}
			}
			// Semantic surfaces
			for _, sem := range b.BoundedBy {
				ss := SemanticSurface{
					XMLName: xml.Name{Local: sem.XMLName.Local},
					ID:      sem.ID,
				}
				if sem.Lod2MultiSurface != nil {
					ss.Lod2MultiSurface = &Lod2MultiSurface{
						MultiSurface: MultiSurface{
							ID: sem.Lod2MultiSurface.MultiSurface.ID,
						},
					}
					for _, sm := range sem.Lod2MultiSurface.MultiSurface.SurfaceMember {
						ss.Lod2MultiSurface.MultiSurface.SurfaceMember = append(
							ss.Lod2MultiSurface.MultiSurface.SurfaceMember,
							OutputSurfaceMember{
								Polygon: OutputPolygon{
									ID: sm.Polygon.ID,
									Exterior: OutputPolygonExterior{
										LinearRing: OutputLinearRing{
											PosList: sm.Polygon.Exterior.LinearRing.PosList,
										},
									},
								},
							})
					}
				}
				outB.BoundedBy = append(outB.BoundedBy, ss)
			}
			outputModel.CityObjectMember = append(outputModel.CityObjectMember, OutputCityObjectMember{Building: outB})
		}
	}

	outputModel.BoundedBy.Envelope.LowerCorner = fmt.Sprintf("%f %f %f", minX, minY, minZ)
	outputModel.BoundedBy.Envelope.UpperCorner = fmt.Sprintf("%f %f %f", maxX, maxY, maxZ)

	output, err := xml.MarshalIndent(outputModel, "", "  ")
	if err != nil {
		fmt.Printf("Error generating merged XML: %v\n", err)
		return
	}
	xmlHeader := `<?xml version="1.0" encoding="UTF-8"?>
<!-- Merged CityGML LoD2 File -->
`
	xmlData := []byte(xmlHeader + string(output))
	if err := ioutil.WriteFile(*outputFile, xmlData, 0644); err != nil {
		fmt.Printf("Error writing output file: %v\n", err)
		return
	}
	fmt.Println("Merged CityGML LoD2 file written to:", *outputFile)
}
