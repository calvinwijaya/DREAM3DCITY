package main

import (
	"bytes"
	"encoding/csv"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
)

type Point struct {
	X float64
	Y float64
	Z float64
}
type Extent struct {
	maxX float64
	maxY float64
	minX float64
	minY float64
}
type MultiPolygon struct {
	outer  []Point
	hole   []Point
	island []*MultiPolygon
}
type Faces struct {
	v  int
	vt int
	vn int
}

type Tiles struct {
	extent     Extent
	childTiles []*Tiles
	index      []int
}

func main() {
	// Define command-line flags
	var cx, cy float64

	// Create a new FlagSet to handle arguments
	flagSet := flag.NewFlagSet("objseparator", flag.ExitOnError)

	// Define flags
	flagSet.Float64Var(&cx, "cx", 692827.46065, "X coordinate offset")
	flagSet.Float64Var(&cy, "cy", 9326588.60235, "Y coordinate offset")

	// Parse flags
	if len(os.Args) < 4 {
		fmt.Println("Usage: go run objseparator.go [options] <obj_file> <geojson_file> <output_dir>")
		fmt.Println("Options:")
		flagSet.PrintDefaults()
		os.Exit(1)
	}

	// Find where the actual file arguments start
	argStart := 1
	for i := 1; i < len(os.Args); i++ {
		if strings.HasPrefix(os.Args[i], "-") {
			continue
		}
		argStart = i
		break
	}

	// Parse flags from args before the file paths
	if err := flagSet.Parse(os.Args[1:argStart]); err != nil {
		fmt.Println("Error parsing flags:", err)
		os.Exit(1)
	}

	// Get file paths from remaining arguments
	remainingArgs := os.Args[argStart:]
	if len(remainingArgs) < 3 {
		fmt.Println("Missing required arguments")
		fmt.Println("Usage: go run objseparator.go [options] <obj_file> <geojson_file> <output_dir>")
		os.Exit(1)
	}

	objFilePath := remainingArgs[0]
	geojsonFilePath := remainingArgs[1]
	outputDir := remainingArgs[2]

	fmt.Printf("Processing with parameters:\n")
	fmt.Printf("  OBJ file: %s\n", objFilePath)
	fmt.Printf("  GeoJSON file: %s\n", geojsonFilePath)
	fmt.Printf("  Output directory: %s\n", outputDir)
	fmt.Printf("  CX: %.5f\n", cx)
	fmt.Printf("  CY: %.5f\n", cy)

	// Read files
	data := ReadFile(objFilePath)
	geoJSONString := ReadFile(geojsonFilePath)

	var geojson map[string]interface{}
	err := json.Unmarshal(geoJSONString, &geojson)
	if err != nil {
		fmt.Println("Error parsing GeoJSON:", err)
		os.Exit(1)
	}

	var v, vn, Mesh = ReadMesh(data)
	geoPolygon, extent := ReadGeomGeojson(geojson, cx, cy)
	cent := []Point{}
	index := []int{}

	fmt.Println("Number of Object to extract: ", len(Mesh))
	// Proses Tiling agar mengurangi search pada geojson
	tiles := CreateTiles(extent, 500, geoPolygon)
	for i := 0; i < len(Mesh); i++ {
		index = append(index, SearchIdInGeom(Mesh, geoPolygon, tiles, v, i, &cent))
	}

	// Filter out outliers (index 12030) before writing
	filteredCent, filteredIndex, filteredMesh := FilterOutliers(cent, index, Mesh)

	fmt.Printf("Objects before filtering: %d\n", len(index))
	fmt.Printf("Objects after filtering: %d\n", len(filteredIndex))
	fmt.Printf("Outliers removed: %d\n", len(index)-len(filteredIndex))

	WritePointsToCSV(filteredCent, filteredIndex, objFilePath+".csv", cx, cy)
	WriteToObj(objFilePath, outputDir, filteredIndex, filteredMesh, v, vn, filteredCent, cx, cy)
}

// FilterOutliers removes objects with index 12030 (outliers)
func FilterOutliers(centroids []Point, indices []int, meshes [][][]Faces) ([]Point, []int, [][][]Faces) {
	const outlierIndex = 12030

	var filteredCentroids []Point
	var filteredIndices []int
	var filteredMeshes [][][]Faces

	for i, idx := range indices {
		if idx != outlierIndex {
			filteredCentroids = append(filteredCentroids, centroids[i])
			filteredIndices = append(filteredIndices, idx)
			filteredMeshes = append(filteredMeshes, meshes[i])
		}
	}

	return filteredCentroids, filteredIndices, filteredMeshes
}

func SearchIdInGeom(Mesh [][][]Faces, geom []MultiPolygon, tile Tiles, v []Point, i int, cent *[]Point) int {
	const defaultRes = 12030
	res := defaultRes

	// Compute centroid in a single loop
	var p []Point
	var cx, cy float64
	faceCount := len(Mesh[i])

	for _, face := range Mesh[i] {
		vx := v[face[0].v-1]
		cx += vx.X
		cy += vx.Y
		p = append(p, Point{vx.X, vx.Y, 0})
	}

	cx /= float64(faceCount)
	cy /= float64(faceCount)
	point := Point{cx, cy, 0}

	// Search in child tiles
	for _, child := range tile.childTiles {
		if child.extent.minX <= point.X && point.X <= child.extent.maxX &&
			child.extent.minY <= point.Y && point.Y <= child.extent.maxY {

			for _, index := range child.index {
				if IsPointInPolygon(point, geom[index]) {
					*cent = append(*cent, point)
					return index
				}
			}
			for _, index := range child.index {
				for _, pt := range p {
					if IsPointInPolygon(pt, geom[index]) {
						*cent = append(*cent, point)
						return index
					}
				}
			}
		}
	}

	*cent = append(*cent, point)
	return res
}

func CreateTiles(extens Extent, size float64, geom []MultiPolygon) Tiles {
	var tile Tiles
	getExtent := func(points []Point) [4]Point {
		var extent Extent
		var res [4]Point
		for i := 1; i < len(points); i++ {
			GetExtent(points[i].X, points[i].Y, &extent)
		}
		res[0] = Point{extent.minX, extent.maxY, 0}
		res[1] = Point{extent.maxX, extent.maxY, 0}
		res[2] = Point{extent.maxX, extent.minY, 0}
		res[3] = Point{extent.minX, extent.minY, 0}
		return res
	}
	tile.extent = extens
	for w := 0.0; extens.minX+w*size < extens.maxX; w++ {
		for h := 0.0; extens.minY+h*size < extens.maxY; h++ {
			minx := extens.minX + w*size
			maxx := minx + size
			miny := extens.minY + h*size
			maxy := miny + size

			if maxx > extens.maxX {
				maxx = extens.maxX
			}
			if maxy > extens.maxY {
				maxy = extens.maxY
			}

			tileExtent := Extent{maxx, maxy, minx, miny}
			tile.childTiles = append(tile.childTiles, &Tiles{tileExtent, nil, []int{}})
		}
	}

	var processPolygon = func(index int, points []Point) {
		if len(points) == 0 {
			return
		}

		extent := getExtent(points)
		for _, extentPoint := range extent {
			for _, child := range tile.childTiles {
				if child.extent.maxX < extentPoint.X || child.extent.minX > extentPoint.X ||
					child.extent.maxY < extentPoint.Y || child.extent.minY > extentPoint.Y {
					continue
				}

				if len(child.index) == 0 || child.index[len(child.index)-1] != index {
					child.index = append(child.index, index)
				}
			}
		}
	}

	for i, g := range geom {
		if len(g.outer) == 0 {
			continue
		}

		processPolygon(i, g.outer)

		for _, island := range g.island {
			processPolygon(i, island.outer)
		}
	}
	return tile
}

func WriteToObj(baseFilename string, outputDir string, index []int, Mesh [][][]Faces, vertices []Point, normals []Point, centroids []Point, cx, cy float64) {
	// Map untuk menyimpan grup berdasarkan indeks unik
	groupedMeshes := make(map[int][][][]Faces)
	groupedCentroids := make(map[int][]Point)

	// Kumpulkan semua grup berdasarkan indeks unik dan centroid-nya
	for i, idx := range index {
		// Skip outliers (index 12030) - this is a safety check
		if idx == 12030 {
			continue
		}

		if _, exists := groupedMeshes[idx]; !exists {
			groupedMeshes[idx] = [][][]Faces{} // Inisialisasi jika belum ada
			groupedCentroids[idx] = []Point{}
		}
		groupedMeshes[idx] = append(groupedMeshes[idx], Mesh[i])
		groupedCentroids[idx] = append(groupedCentroids[idx], centroids[i])
	}

	// Create output directory if it doesn't exist
	err := os.MkdirAll(outputDir, os.ModePerm)
	if err != nil {
		fmt.Printf("Error creating output directory: %v\n", err)
		return
	}

	// Extract base filename without extension and path
	baseName := strings.TrimSuffix(baseFilename, ".obj")
	if strings.Contains(baseName, "/") {
		parts := strings.Split(baseName, "/")
		baseName = parts[len(parts)-1]
	}
	if strings.Contains(baseName, "\\") {
		parts := strings.Split(baseName, "\\")
		baseName = parts[len(parts)-1]
	}

	// Proses setiap indeks unik dan ekspor sebagai file .obj terpisah
	for idx, groups := range groupedMeshes {
		// Calculate average centroid for this group (in case there are multiple objects with same index)
		avgCentroid := Point{0, 0, 0}
		centroidCount := len(groupedCentroids[idx])
		if centroidCount > 0 {
			for _, centroid := range groupedCentroids[idx] {
				avgCentroid.X += centroid.X
				avgCentroid.Y += centroid.Y
			}
			avgCentroid.X /= float64(centroidCount)
			avgCentroid.Y /= float64(centroidCount)
		}

		// Convert back to original coordinate system and format as integers
		originalX := int(avgCentroid.X + cx)
		originalY := int(avgCentroid.Y + cy)

		// Generate filename with the new format
		filename := fmt.Sprintf("%s/%s_%d_%d.obj", outputDir, baseName, originalX, originalY)

		file, err := os.Create(filename)
		if err != nil {
			fmt.Println("Error creating file:", err)
			continue
		}
		defer file.Close()

		// Map untuk menyimpan vertex & normal lokal agar indeksnya tetap berurutan
		vertexMap := make(map[int]int)
		normalMap := make(map[int]int)
		localVertices := []Point{}
		localNormals := []Point{}
		vertexCounter := 1
		normalCounter := 1

		// 1. Kumpulkan semua vertex & normal yang digunakan dalam grup ini
		for _, facesGroup := range groups {
			for _, sides := range facesGroup { // Sisi-sisi dalam grup
				for _, faces := range sides {
					// Konversi indeks vertex ke lokal
					if _, exists := vertexMap[faces.v]; !exists {
						vertexMap[faces.v] = vertexCounter
						localVertices = append(localVertices, vertices[faces.v-1]) // -1 karena index mulai dari 1
						vertexCounter++
					}
					// Konversi indeks normal ke lokal
					if _, exists := normalMap[faces.vn]; !exists {
						normalMap[faces.vn] = normalCounter
						localNormals = append(localNormals, normals[faces.vn-1])
						normalCounter++
					}
				}
			}
		}

		// 2. Tulis semua vertex (v x y z)
		for _, v := range localVertices {
			file.WriteString(fmt.Sprintf("v %.6f %.6f %.6f\n", v.X, v.Y, v.Z))
		}

		// 3. Tulis semua normal (vn nx ny nz)
		for _, vn := range localNormals {
			file.WriteString(fmt.Sprintf("vn %.6f %.6f %.6f\n", vn.X, vn.Y, vn.Z))
		}

		// 4. Menulis objek dengan nama unik berdasarkan centroid
		file.WriteString(fmt.Sprintf("o %s_%d_%d\n", baseName, originalX, originalY))

		// 5. Menulis face dengan indeks yang sesuai
		for _, facesGroup := range groups {
			for _, sides := range facesGroup { // Sisi dalam grup
				facesTxt := "f "
				for _, face := range sides {
					vLocal := vertexMap[face.v]
					vnLocal := normalMap[face.vn]
					facesTxt += strconv.Itoa(vLocal) + "//" + strconv.Itoa(vnLocal) + " "
				}
				file.WriteString(facesTxt + "\n")
			}
		}
	}

	fmt.Printf("Exported %d OBJ files to %s (outliers excluded)\n", len(groupedMeshes), outputDir)
}

func WritePointsToCSV(points []Point, index []int, filename string, cx, cy float64) error {
	file, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer file.Close()

	writer := csv.NewWriter(file)
	defer writer.Flush()

	// Write CSV header
	if err := writer.Write([]string{"X", "Y", "Z", "Index"}); err != nil {
		return err
	}

	// Write each point to CSV (outliers already filtered out)
	for i, p := range points {
		row := []string{
			strconv.FormatFloat(p.X+cx, 'f', 6, 64),
			strconv.FormatFloat(p.Y+cy, 'f', 6, 64),
			strconv.FormatFloat(p.Z, 'f', 6, 64),
			strconv.FormatInt(int64(index[i]), 10),
		}
		if err := writer.Write(row); err != nil {
			return err
		}
	}

	fmt.Println("CSV file saved:", filename, "(outliers excluded)")

	return nil
}

// Rest of the functions remain the same...
func IsPointInPolygon(point Point, polygon MultiPolygon) bool {
	const eps = 1e-9
	inside := false
	var queryPolygon = func(inside *bool, polygon MultiPolygon) {
		ring := polygon.outer
		n := len(ring)
		if n < 3 {
			*inside = false // Skip invalid polygon parts
		}

		j := n - 1 // Previous vertex index
		for i := 0; i < n; i++ {
			yi, yj := ring[i].Y, ring[j].Y
			if (yi > point.Y+eps) != (yj > point.Y+eps) { // Check y-bounds
				xi, xj := ring[i].X, ring[j].X
				xIntersect := (xj-xi)*(point.Y-yi)/(yj-yi+eps) + xi
				if point.X < xIntersect+eps {
					*inside = !*inside
				}
			}
			j = i
		}
	}
	queryPolygon(&inside, polygon)
	if !inside {
		for _, island := range polygon.island {
			queryPolygon(&inside, *island)
			if inside {
				return inside
			}
		}
	}

	return inside
}

func ReadMesh(data []byte) ([]Point, []Point, [][][]Faces) {
	var v = []Point{}
	var vn = []Point{}
	var Mesh [][][]Faces
	var err error
	groupIndex := []int{}
	for i := 0; i < len(data)-2; i++ {
		if bytes.Equal(data[0+i:2+i], []byte{10, 111}) {
			groupIndex = append(groupIndex, 0+i)
		}
	}
	for i := 0; i < len(data)-5; i++ {
		if bytes.Equal(data[0+i:5+i], []byte{13, 10, 13, 10, 103}) {
			groupIndex = append(groupIndex, 0+i)
		}
	}
	for i := 0; i < len(groupIndex); i++ {
		group := []byte{}
		if i != len(groupIndex)-1 {
			group = data[groupIndex[i]:groupIndex[i+1]]
		} else {
			group = data[groupIndex[i]:]
		}

		groupSplit := strings.Split(string(group), "\n")
		var meshGroup [][]Faces
		for j := 0; j < len(groupSplit); j++ {
			line := strings.Split(strings.TrimSpace(string(groupSplit[j])), " ")
			if len(line) > 1 {
				if line[0] == "v" {
					var vertex Point
					vertex.X, err = strconv.ParseFloat(line[1], 64)
					vertex.Y, err = strconv.ParseFloat(line[2], 64)
					vertex.Z, err = strconv.ParseFloat(line[3], 64)
					v = append(v, vertex)
					if err != nil {
						fmt.Println(err)
					}
				} else if line[0] == "vn" {
					var vertex Point
					vertex.X, err = strconv.ParseFloat(line[1], 64)
					vertex.Y, err = strconv.ParseFloat(line[2], 64)
					vertex.Z, err = strconv.ParseFloat(line[3], 64)
					vn = append(vn, vertex)
				} else if line[0] == "f" {
					var f = make([]Faces, len(line)-1)
					for k := 1; k < len(line); k++ {
						if len(line[k]) > 0 {
							indexes := strings.Split(line[k], "/")
							value, err := strconv.ParseInt(indexes[0], 10, 64)
							f[k-1].v = int(value)
							value, err = strconv.ParseInt(indexes[2], 10, 64)
							f[k-1].vn = int(value)
							if err != nil {
								fmt.Println(err)
							}
						}
					}
					meshGroup = append(meshGroup, f)
				}
			}
		}
		Mesh = append(Mesh, meshGroup)
	}
	return v, vn, Mesh
}

func GetExtent(X float64, Y float64, extents *Extent) {
	if extents.maxX == 0 || extents.minX == 0 {
		extents.maxX = X
		extents.minX = X
	} else {
		if extents.maxX < X {
			extents.maxX = X
		}
		if X < extents.minX {
			extents.minX = X
		}
	}
	if extents.maxY == 0 || extents.minY == 0 {
		extents.maxY = Y
		extents.minY = Y
	} else {
		if extents.maxY < Y {
			extents.maxY = Y
		}
		if Y < extents.minY {
			extents.minY = Y
		}
	}
}

func ReadGeomGeojson(geojson map[string]interface{}, cx, cy float64) ([]MultiPolygon, Extent) {
	var MultiPolygons []MultiPolygon
	var extents Extent
	features := geojson["features"].([]interface{})

	fmt.Printf("Using coordinate offsets: CX=%.5f, CY=%.5f\n", cx, cy)

	for _, feature := range features {
		geometry, ok := feature.(map[string]interface{})["geometry"].(map[string]interface{})
		if !ok {
			continue
		}

		coordinates, ok := geometry["coordinates"].([]interface{})
		if !ok || len(coordinates) == 0 {
			MultiPolygons = append(MultiPolygons, MultiPolygon{}) // Append empty MultiPolygon
			continue
		}

		var polygons MultiPolygon

		for idxPolygon, polygon := range coordinates {
			polygonParts, ok := polygon.([]interface{})
			if !ok {
				continue
			}

			for idxPart, part := range polygonParts {
				coord, ok := part.([]interface{})
				if !ok || len(coord) < 3 {
					continue
				}

				LinerRing := make([]Point, len(coord))
				for j := range coord {
					point := coord[j].([]interface{})
					X, Y := point[0].(float64)-cx, point[1].(float64)-cy
					LinerRing[j] = Point{X, Y, 0}

					GetExtent(X, Y, &extents)
				}

				if idxPolygon == 0 {
					if idxPart == 0 {
						polygons.outer = LinerRing
					} else {
						polygons.hole = LinerRing
					}
				} else {
					var island MultiPolygon
					if idxPart == 0 {
						island.outer = LinerRing
					} else {
						island.hole = LinerRing
					}
					polygons.island = append(polygons.island, &island)
				}
			}
		}

		MultiPolygons = append(MultiPolygons, polygons)
	}
	return MultiPolygons, extents
}

func ReadFile(filePath string) []byte {
	file, errFile := os.Open(filePath)
	stat, errStat := os.Stat(filePath)
	defer file.Close()
	if errFile != nil {
		log.Fatal(errFile)
	}
	if errStat != nil {
		log.Fatal(errStat)
	}

	fileLength := stat.Size()
	bytesBuffer := make([]byte, fileLength)
	bin, err := file.Read(bytesBuffer)
	if err != nil {
		log.Fatal(err)
	}
	var data []byte = bytesBuffer[:bin]
	return data
}
