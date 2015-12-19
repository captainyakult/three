__author__ = 'Jack Simpson'
__version__ = '2.0.0'
__email__ = 'jack@jacksimpson.nyc'

import sys

import os.path
import json
import shutil
import math

from pymel.core import *
from maya.OpenMaya import *
from maya.OpenMayaMPx import *
import maya.cmds as cmds

kPluginTranslatorTypeName = 'Three.js'
kOptionScript = 'ThreeJsExportScript'
kDefaultOptionsString = '0'

# constants
FLOAT_PRECISION = 6
BUILDING_STR = 'building'
TRANCHE_STR = 'tranche'
FLOOR_STR = 'floor'
UNIT_STR = 'unit'
INSTANCE_PREFIX = 'inst_'
FILE_EXT = 'json'
MODEL_LIST = 'modelList'


class ThreeJsExporter(object):
    def __init__(self):
        self.componentKeys = ['vertices', 'normals', 'colors', 'uvs', 'faces', 'materials', 'skeleton', 'animation']
        self.buildingSections = [BUILDING_STR, TRANCHE_STR, FLOOR_STR, UNIT_STR]
        print 'Threejs exporter class initialized'

    def run(self, pathList, optionString):

        print 'Executing run method'

        self.paths = pathList

        ## get frame info
        self.startFrame = playbackOptions(minTime=True, query=True)
        self.endFrame = playbackOptions(maxTime=True, query=True)
        self.frameRate = 24.0
        self.errors = []

        ## parse options
        self.options = self._parseOptions(optionString)
        self.vertexColors = self.options['colors']
        self.exUvs = self.options['uvs']
        self.requiresUVs = []


        
        selected = ls(sl=1)
        if len(selected) == 0:
            print "Please select something to export!"
            return
        # ## ANIMATIONS EXPORT
        # if self.options["animation"]:

        #     self.__jointsList = self._getJoints()
        #     self.processBones()
        #     # return

        #     self.animations = []

        #     animName = self.options['animationData']['name']

        #     startFrame = int(self.options['animationData']['startFrame'])
        #     endFrame = int(self.options['animationData']['endFrame'])

        #     filePath = os.path.join(self.path, self.genderPrefix, self.skeletonAnimationFolder, "%s_%s_%s.json" % (self.genderPrefix, self.animationsName, animName))

        #     print("exporting %s animation from frames %i to %i" % (animName, startFrame, endFrame))
        #     self.__jointsList = self._getJoints()
        #     self._exportKeyframeAnimations(animName, startFrame, endFrame)

        #     output = {
        #         'metadata': {
        #             'name': 'Maya to Three.js Export',
        #             'version': 2.0,
        #             'createdBy': 'HyperHyper'
        #         },
        #         'animations': []
        #     }

        #     output['animations'] = self.animations

        #     self.writeFile(filePath, output)

        #     print 'animation exported!'

        ## GEOMETRY EXPORT
        if self.options["faces"]:
            modelList = []
            for sel in selected:
                self.__meshDataList = []
                self.buildGeoArray(sel)

                for i, meshData in enumerate(self.__meshDataList):
                    
                    isInstance = meshData['instance']
                    filename = self.genOutputName(meshData['geometry'])
                    fileOut = "%s.%s" % (filename, FILE_EXT)
                    modelList.append(filename)
                    print "Exporting %s..." % meshData['geometry']['node']

                    if isInstance and i == 0: # we have to make sure the root is changed to a longname (we only need to do it on the first one as it is referenced in all the indices)
                        meshData['instanceData']['root'] = meshData['instanceData']['root'].longName()

                    self._exportNode(
                        meshData['geometry']['node'], 
                        fileOut, meshData['geometry']['metadata'], 
                        instanceData=meshData['instanceData'] if isInstance else False
                        )

        if len(self.errors):
            print "Export complete - but there's a problem...\nYou thought bad bitches were your fucking problem?\nThis is 10 times worse."
            for e in self.errors:
                print "ERROR: %s" % e
        
        print "Writing model list..."
        self.writeModelList(modelList)
        print "Export complete!"

        
    def _exportNode(self, node, fileout, metadata, instanceData=False):

        # print 'Removing namespaces.'
        self._removeNamespaces(node)
        # print "Triangulating and deleting non-deformer history."
        self._processMesh(node)

        self.verticeOffset = 0
        self.uvOffset = 0
        self.normalOffset = 0
        self.colorOffset = 0
        self.vertices = []
        self.faces = []
        self.normals = []
        self.uvs = []
        self.colors = []
        self.skinIndices = []
        self.skinWeights = []

        self._exportMesh(node)

        output = {
            'metadata': {
                'name': 'Maya to Three.js Export',
                'version': 2.0,
                'createdBy': 'Jack Simpson',
                'geometry': {
                    "data": metadata,
                    "instanceData": instanceData if instanceData else 'false'
                }
            },
            'colors': self.colors,
            'vertices': self.vertices,
            'uvs': [self.uvs],
            'faces': self.faces,
            'normals': self.normals,
            'bones': [],
            'materials': []
        }
        
        for path in self.paths:
            filePath = os.path.join(path, fileout)
            self.writeFile(filePath, output)

    def writeModelList(self, modelList):
        output = ["%s.%s" % (m, FILE_EXT) for m in modelList]
        for path in self.paths:
            filePath = os.path.join(path, "%s.%s" % (MODEL_LIST, FILE_EXT))
            self.writeFile(filePath, output)

    
    def genOutputName(self, node):
        outputStr = ""
        for section in self.buildingSections:
            if section in node['metadata']:
                outputStr += "%s_" % node['metadata'][section]['value']
        outputStr += node['node'].name().split('|')[-1]
        return outputStr
        
    def getInstanceInfo(self, instArray):
        info = {
            "root": False,
            "offsets": {}
        }
        for i in instArray:
            tArray = getAttr(i+'.translate')
            rArray = getAttr(i+'.rotate')
            sArray = getAttr(i+'.scale')
            rootTranslate = all([int(val) == 0 for val in tArray])
            rootRotate = all([int(val) == 0 for val in rArray])
            rootScale = all([int(val) == 1 for val in sArray])
            
            if rootTranslate and rootRotate and rootScale:
                rootmeta = self.genMeta(i)
                info['metadata'] = rootmeta
                info['root'] = i
            else:
                info['offsets'][i.name()] = {
                    "pos": [roundToPrec(coord) for coord in tArray],
                    "rot": [roundToPrec(coord) for coord in rArray],
                    "scl": [roundToPrec(coord) for coord in sArray]
                }

        if not info['root']:
            raise RuntimeError('ERROR!\nInstances identified. Please make sure the root instance has freeze transforms.')

        
                
        return info
        

    def isMesh(self, obj):
        if len(self.children(obj)):
            return False
        return True

    def children(self, node):
        return [c for c in node.getChildren() if c.nodeType() == 'transform']

    def getSectionNode(self, node, sectionName):
        par = node.getParent()
        

        if sectionName == BUILDING_STR:
            return node if par is None else self.getSectionNode(par, sectionName)
        if node is None or par is None:
            return None
        splitNode = par if sectionName == UNIT_STR else node
        shortName = splitNode.name().split('|')[-1]
        split = shortName.split('%s_' % sectionName)
        return splitNode if len(split) > 1 else self.getSectionNode(par, sectionName)
        
    def genMeta(self, node):
        metaObj = {}

        for sectionName in self.buildingSections:
            sectionNode = self.getSectionNode(node, sectionName)
            if sectionNode != None:
                metaObj[sectionName] = { 
                    'value': sectionNode.name().split('%s_' % sectionName)[-1].split('|')[0],
                    'centerPoint': [roundToPrec(coord) for coord in sectionNode.getRotatePivot()],
                    'dimensions': [roundToPrec(coord) for coord in getAttr("%s.boundingBoxSize" % sectionNode)]
                }
        
        return metaObj

    def isInstance(self, node):
        return node.name().split('|')[-1].startswith(INSTANCE_PREFIX )

    
    def buildGeoArray(self, node, instanceData=False):
        # this function is self invoking and probably too complicated. arg.
        newInstArray = []
        existingInstArray = []
        nonInstArray = []
        
        if not getAttr("%s.visibility" % node) or node.name().endswith('curves'):
            return
        
        if self.isMesh(node):
            # we hit the bottom of the hierarchy so no more groups! it's either part of an instance root or a unique piece of geo
            if instanceData:
                self.__meshDataList.append({
                    "geometry": {
                        "node": node,
                        "metadata": self.genMeta(node)
                    },
                    "instance": True,
                    "instanceData": instanceData
                })
                return
            # else it's unique
            self.__meshDataList.append({
                "geometry": {
                    "node": node,
                    "metadata": self.genMeta(node)
                },
                "instance": False
            })
            return

        # selected could be an instance
        elif self.isInstance(node) and not instanceData:
            par = node.getParent()
            for child in self.children(par):
                if self.isInstance(child):
                    newInstArray.append(child)
        
        # if it's not a mesh or an instance, it's a group - iterate through that group's children
        else:
            for child in self.children(node):
                if instanceData:
                    existingInstArray.append(child)
                elif self.isInstance(child):
                    newInstArray.append(child)
                else:
                    nonInstArray.append(child)

        if len(existingInstArray):
            for obj in existingInstArray:
                self.buildGeoArray(obj, instanceData=instanceData)

        if len(newInstArray):
            instData = self.getInstanceInfo(newInstArray)
            self.buildGeoArray(instData['root'], instanceData=instData)
            
        if len(nonInstArray):
            for obj in nonInstArray:
                self.buildGeoArray(obj)

    def writeFile(self, filePath, output):
        directory = os.path.split(filePath)[0]
        if not os.path.exists(directory):
            os.makedirs(directory)
        with file(filePath, 'w') as f:
                f.write(json.dumps(output, separators=(",", ":"), allow_nan=False))

    def _processMesh(self, mesh):
        
        try:
            polyTriangulate(mesh)
            bakePartialHistory(mesh, ppt=1)
        except:
            self.errors.append("Problem processing mesh, %s." % mesh.name())

    
    def _removeNamespaces(self, node):
        # all_ns = [node.namespace() for node in nodes if node.namespace()]
        # # remove dupes
        # all_ns = list(set(all_ns))
        ns = node.namespace()
        if not ns:
            return
        else:
            all_ns = [ns]
        ns_info = namespaceInfo(lon=1)
        # try to remove the first namespace
        for whole_ns in all_ns:
            ns = whole_ns.split(':')[0]
            try:
                namespace(mv=[ns, ':'], f=1)
                if ns in ns_info:
                    namespace(rm=ns)
                print 'Namespace "%s" removed.' % ns
            except:
                print 'Namespace "%s" is not removable.' % ns
                continue

    

    def populateMeshArray(self):
        print "populating the mesh array."
        # get all meshes that are visible
        # create and populate a parent transforms array
        # for each parent, place the children array into the mesh list for processing
        allMeshes = [mesh for mesh in ls(type='mesh', v=1) if len(mesh.listConnections()) > 0]

        geoNodes = []
        for mesh in allMeshes:
            par = mesh.getParent()
            # make sure par is not a group node (group nodes have children that are all transform types)
            if any([child.type() != "transform" for child in par.getChildren()]) and par not in geoNodes:
                # print par
                geoNodes.append(par)

        return geoNodes

        meshList = []
        for gnode in geoNodes:
            children = gnode.listRelatives(c=1)
            # we need to find the skinned mesh
            skinnedMesh = False
            for child in children:
                if child.name().endswith('Deformed'):
                    skinnedMesh = child
            if not skinnedMesh:
                skinnedMesh = children[0]

            meshList.append(skinnedMesh)

        return meshList


    def _exportKeyframeAnimations(self, name, start, end):
        joints = self.__jointsList
        if not len(joints):
            self.errors.append("No joints were found. No skeleton exported.")
            return False

        hierarchy = []
        i = -1
        # self.frameRate = FramesPerSecond(currentUnit(query=True, time=True)).value()
        for joint in joints:
            hierarchy.append({
                "parent": i,
                "keys": self._getKeyframes(joint, start, end)
            })
            i += 1

        animLength =  round((end - start) / self.frameRate,  FLOAT_PRECISION)

        self.animations.append({
            "name": name,
            "length": animLength,
            "fps": int(self.frameRate),
            "hierarchy": hierarchy
        })

    def _getKeyframes(self, joint, start, end):

        frames = sorted(list(set(keyframe(joint, query=True) + [start, end])))
        keys = []

        print("joint " + joint.name() + " has " + str(len(frames)) + " keyframes")
        for frame in frames:
            self._goToFrame(frame)
            keys.append(self._getCurrentKeyframe(joint, frame, start))
        return keys

    def _getCurrentKeyframe(self, joint, frame, beginningFrame):
        pos = joint.getTranslation()
        rot = joint.getRotation(quaternion=True) * joint.getOrientation()
        scl = cmds.getAttr(joint + '.scale')[0]
        keyTime =  round( (frame - beginningFrame) / self.frameRate,  FLOAT_PRECISION)
        return {
            'time': keyTime,
            'pos': self._roundPos(pos),
            'rot': self._roundQuat(rot),
            'scl': self._roundScl(scl)
        }

    def _roundPos(self, pos):
        return map(lambda x: round(x, FLOAT_PRECISION), [pos.x, pos.y, pos.z])

    def _roundScl(self, scl):
        return map(lambda x: round(x, FLOAT_PRECISION), [scl[0], scl[1], scl[2]])

    def _roundQuat(self, rot):
        return map(lambda x: round(x, FLOAT_PRECISION), [rot.x, rot.y, rot.z, rot.w])

    def _goToFrame(self, frame):
        currentTime(frame)

    
    def _exportMesh(self, mesh):
        if self.options['vertices']:
            # for point in mesh.getPoints(space='world'):
            #     x = round(point.x, FLOAT_PRECISION)
            #     y = round(point.y, FLOAT_PRECISION)
            #     z = round(point.z, FLOAT_PRECISION)
            #     for coord in [x, y, z]:
            #         self.vertices
            self.vertices = [coord for point in mesh.getPoints(space='world') for coord in [round(point.x, FLOAT_PRECISION) if str(round(point.x, FLOAT_PRECISION)) != 'nan' else 0, round(point.y, FLOAT_PRECISION) if str(round(point.y, FLOAT_PRECISION)) != 'nan' else 0, round(point.z, FLOAT_PRECISION) if str(round(point.z, FLOAT_PRECISION)) != 'nan' else 0]]

        if self.vertexColors:
            try:
                self.options['colors'] = len(mesh.getColors()) > 0
            except:
                print "Vertex colors not found in %s mesh. No colors data appended" % mesh.name()
                self.options['colors'] = False

        if self.exUvs:
            nameInCurrMesh = False
            for uvName in self.requiresUVs:
                if uvName in mesh.name():
                    nameInCurrMesh = True
                    break
            if nameInCurrMesh:
                print "Adding UVs"
            else:
                print "UVs not required in %s" % mesh.name()
                self.options['uvs'] = False

        if self.options['faces']:
            self._exportFaces(mesh)
            self.verticeOffset += len(mesh.getPoints())
            self.uvOffset += mesh.numUVs()
            self.normalOffset += mesh.numNormals()
            self.colorOffset += mesh.numColors()

        if self.options['normals']:
            print("Exporting normals")
            print "number of normals for %s is %d" % (mesh.name(), len(mesh.getNormals()))
            for normal in mesh.getNormals():
                x = round(normal.x, FLOAT_PRECISION)
                y = round(normal.y, FLOAT_PRECISION)
                z = round(normal.z, FLOAT_PRECISION)
                if str(x) == 'nan':
                    self.errors.append('%s contains normals with values that evaluate to NaN - please fix this model.' % mesh.name())
                self.normals += [x if str(x) != 'nan' else 0, y if str(y) != 'nan' else 0, z if str(z) != 'nan' else 0]

        if self.options['uvs']:
            print("Exporting UVs")
            us, vs = mesh.getUVs()
            for i, u in enumerate(us):
                self.uvs.append(u)
                self.uvs.append(vs[i])
        if self.options['colors']:
            print("Exporting colors")
            for color in mesh.getColors():
                hexString = self.getHex(color.r * 255, color.g * 255, color.b * 255)
                self.colors.append(hexString)

        self.options['colors'] = self.vertexColors
        self.options['uvs'] = self.exUvs

    def getHex(self, r, g, b):
        red = self.clampColor(r)
        green = self.clampColor(g)
        blue = self.clampColor(b)
        return '#%02x%02x%02x' % (red, green, blue)

    def clampColor(self, color):
        smallest = 0
        largest = 255
        return max(smallest, min(int(color), largest))

    def _exportFaces(self, mesh):
        typeBitmask = self._getTypeBitmask()

        for face in mesh.faces:
            # materialIndex = self._getMaterialIndex(face, mesh)
            # hasMaterial = materialIndex != -1
            self._exportFaceBitmask(face, typeBitmask, hasMaterial=False)
            self.faces += map(lambda x: x + self.verticeOffset, face.getVertices())
            # if self.options['materials']:
            #     if hasMaterial:
            #         self.faces.append(materialIndex)
            if self.options['uvs'] and face.hasUVs():
                self.faces += map(lambda v: face.getUVIndex(v) + self.uvOffset, range(face.polygonVertexCount()))
            if self.options['normals']:
                for i in range(face.polygonVertexCount()):
                    self.faces.append(face.normalIndex(i) + self.normalOffset)
            if self.options['colors']:
                for i in range(face.polygonVertexCount()):

                    try:
                        cIndex = face.getColorIndex(i) + self.colorOffset
                    except:
                        cIndex = self.colorOffset
                    self.faces.append(cIndex)


    def _exportFaceBitmask(self, face, typeBitmask, hasMaterial=True):
        if face.polygonVertexCount() == 4:
            faceBitmask = 1
        else:
            faceBitmask = 0

        if hasMaterial:
            faceBitmask |= (1 << 1)

        if self.options['uvs'] and face.hasUVs():
            faceBitmask |= (1 << 3)

        self.faces.append(typeBitmask | faceBitmask)



    def _parseOptions(self, optionsString):
        print 'parsing options'
        options = dict([(x, False) for x in self.componentKeys])
        optionsSplit = optionsString.split(' ')
        
        for key in self.componentKeys:
            options[key] = key in optionsString


        if options["animation"]:
            animString = optionsString[optionsString.find("animation"):]
            animName = animString.split(' ')[1]

            options['animationData'] = dict({
                'name': animName,
                'startFrame': self.startFrame,
                'endFrame': self.endFrame
            })

            if options['spin']:
                spinString = optionsString[optionsString.find("spin"):]
                self.spinKeyStart = int(spinString.split(' ')[1])
                self.spinKeyEnd = self.spinKeyStart + 1


        return options

    def _getTypeBitmask(self):
        bitmask = 0
        if self.options['normals']:
            bitmask |= 32
        if self.options['colors']:
            bitmask |= (1 << 7)
        return bitmask

class FramesPerSecond(object):
    MAYA_VALUES = {
        'game': 15,
        'film': 24,
        'pal': 25,
        'ntsc': 30,
        'show': 48,
        'palf': 50,
        'ntscf': 60
    }

    def __init__(self, fpsString):
        self.fpsString = fpsString

    def value(self):
        if self.fpsString in FramesPerSecond.MAYA_VALUES:
            return FramesPerSecond.MAYA_VALUES[self.fpsString]
        else:
            return int(filter(lambda c: c.isdigit(), self.fpsString))

def roundToPrec(floatVal):
    return round(floatVal, FLOAT_PRECISION)


# gender followed by max influences
# to export geometry, include 'faces' in the export options
# to export skeleton, include 'skeleton'
# to export animation, include 'animation' in the export options followed by animation name
# exportOptions = "female 3 vertices normals colors uvs faces skeleton animation idleA"
exportOptions = "vertices faces"
exportPaths = ["/mnt/NY_Interactive/dev/jack/THREE/assets/models", "/mnt/NY_Interactive/dev/jack/THREE/html/js/models"]

undoInfo(openChunk=True)
ThreeJsExporter().run(exportPaths, exportOptions)
undoInfo(closeChunk=True)


    

    
    


#for child in selNode.getChildren():
#    fullName = child.longName()
#    splitName = fullName.split('|')
#    tranche = splitName[2]
#    print splitName