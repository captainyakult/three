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


FLOAT_PRECISION = 6
TRANCHESTR = 'Tranche'
FLOORSTR = 'Floor'

class ThreeJsExporter(object):
    def __init__(self):
        self.componentKeys = ['vertices', 'normals', 'colors', 'uvs', 'faces', 'materials', 'skeleton', 'animation']
        print 'Threejs exporter class initialized'

    def run(self, path, optionString):

        print 'Executing run method'

        self.path = path

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

        ## 
        



        
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
            print 'exporting meshes'
            for sel in selected:
                self.__meshList = []
                self.buildGeoArray(sel)

                for mesh in self.__meshList:
                    print mesh
                    ## remove namspaces
                    #print 'Removing namespaces...'
                    #self._removeNamespaces(mesh)
            return

            for mesh in meshList:
                # set name
                try:
                    name = mesh.name()
                except:
                    name = mesh.split("_")[0]


                ## put into correct folder
                # if self.genderPrefix == 'lightBeam':
                #     outFolder = self.lightBeamFolder

                filePath = os.path.join(self.path, "%s.json" % (name))

                print "exporting %s mesh..." % name

                ## prune mesh and raise excpetion if weights over 4
                # if self.genderPrefix != 'lightBeam':
                #     print "Pruning small skin weights.."
                #     self._smartPrune(mesh)
                # process mesh with triangulation and deleting deformer history
                self.processMesh(mesh)


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

                

                self._exportMesh(mesh)


                output = {
                    'metadata': {
                        'name': 'Maya to Three.js Export',
                        'version': 2.0,
                        'createdBy': 'Jack Simpson'
                    },
                    'colors': self.colors,
                    'vertices': self.vertices,
                    'uvs': [self.uvs],
                    'faces': self.faces,
                    'normals': self.normals,
                    'bones': [],
                    'materials': [],
                }
                # custom metadata
                # if '' in name:
                #     output['metadata']['custom'] = hMapObj

                
                # output['bones'] = []
                # output['skinIndices'] = self.skinIndices
                # output['skinWeights'] = self.skinWeights
                # output['influencesPerVertex'] = self.influences


                self.writeFile(filePath, output)

        if len(self.errors):
            print "Export complete - but there's a problem...\nYou thought bad bitches were your fucking problem?\nThis is 10 times worse."
            for e in self.errors:
                print "ERROR: %s" % e
        print "export complete"
        
    
    
    
        
    def genOutputFolder(self, node):
        maxIndex = 5
        split = node.longName().split('|')[1:maxIndex]
        return '/'.join(split)
        
    def getInstanceInfo(self, instArray):
        info = {
            "root": False,
            "instData": {}
        }
        for i in instArray:
            tArray = getAttr(i+'.translate')
            rArray = getAttr(i+'.rotate')
            sArray = getAttr(i+'.scale')
            rootTranslate = all([int(val) == 0 for val in tArray])
            rootRotate = all([int(val) == 0 for val in rArray])
            rootScale = all([int(val) == 1 for val in sArray])
            
            if rootTranslate and rootRotate and rootScale:
                info['root'] = i
            else:
                info['instData'][i.name()] = {
                    "pos": tArray,
                    "rot": rArray,
                    "scl": sArray
                }
                
        return info
        

    def isMesh(self, obj):
        if len(children(obj)):
            return False
        return True

    def children(self, node):
        return [c for c in node.getChildren() if c.nodeType() == 'transform']
        
    def getBuilding(self, node):
        parNode = node.getParent()
        return node if parNode is None else getBuilding(parNode)
        
    def getTranche(self, node):
        if node is None:
            return None
        par = node.getParent()
        shortName = node.name().split('|')[-1]
        split = shortName.split(TRANCHESTR)
        return node if len(split) > 1 else getTranche(par)

    def getFloor(self, node):
        if node is None:
            return None
        par = node.getParent()
        shortName = node.name().split('|')[-1]
        split = shortName.split(FLOORSTR)
        return node if len(split) > 1 else getFloor(par)
            
            
    def getUnit(self, node):
        if node is None:
            return None
        par = node.getParent()
        if par is None:
            return None
        shortName = par.name().split('|')[-1]
        split = shortName.split(FLOORSTR)
        return node if len(split) > 1 else getUnit(par)
            
        
        
        
    def genMeta(self, node):
        metaObj = {}
        
        building = self.getBuilding(node)
        if building != None:
            metaObj['building'] = { 
                'name': building.name().split('|')[-1],
                'centerPoint': [roundToPrec(coord) for coord in building.getRotatePivot()],
                'dimensions': [roundToPrec(coord) for coord in getAttr("%s.boundingBoxSize" % building)]
            }
        
        tranche = self.getTranche(node)
        if tranche != None:
            metaObj['tranche'] = { 
                'name': tranche.name().split(TRANCHESTR)[-1].split('|')[0],
                'centerPoint': [roundToPrec(coord) for coord in tranche.getRotatePivot()],
                'dimensions': [roundToPrec(coord) for coord in getAttr("%s.boundingBoxSize" % tranche)]
            }
            
        floor = getFloor(node)
        if floor != None:
            metaObj['floor'] = { 
                'number': floor.name().split(FLOORSTR)[-1].split('|')[0],
                'centerPoint': [roundToPrec(coord) for coord in floor.getRotatePivot()],
                'dimensions': [roundToPrec(coord) for coord in getAttr("%s.boundingBoxSize" % floor)]
            }
        unit = getUnit(node)
        if unit != None:
            metaObj['unit'] = { 
                'name': unit.longName().split(FLOORSTR)[-1].split('|')[-1],
                'centerPoint': [roundToPrec(coord) for coord in unit.getRotatePivot()],
                'dimensions': [roundToPrec(coord) for coord in getAttr("%s.boundingBoxSize" % unit)]
            }
        
        return metaObj

    
    def buildGeoArray(self, node):
        instArray = []
        noninstArray = []
        
        if not getAttr("%s.visibility" % node) or node.name().endswith('curves'):
            return
        
        if isMesh(node):
            self.__meshList.append({
                "geometry": node,
                "metadata": self.genMeta(node)
            })
            return
        
        
        for child in children(node):
            if child.name().split('|')[-1].startswith('inst_'):
                instArray.append(child)
            else:
                noninstArray.append(child)

        if len(instArray):
            instData = self.getInstanceInfo(instArray)
            # TODO: add root geo to mesh array and include instaData as metadata
            # self.__meshList.append({
            #     "geometry": instData.root,
            #     "metadata": self.genMeta(node)
            # })
            print instData
            
        if len(noninstArray):
            for obj in noninstArray:
                self.buildGeoArray(obj)

    def writeFile(self, filePath, output):
        directory = os.path.split(filePath)[0]
        if not os.path.exists(directory):
            os.makedirs(directory)
        with file(filePath, 'w') as f:
                f.write(json.dumps(output, separators=(",", ":"), allow_nan=False))

    def processMesh(self, mesh):
        print "Triangulating %s and deleting non-deformer history..." % mesh.name()
        try:
            polyTriangulate(mesh)
            bakePartialHistory(mesh, ppt=1)
        except:
            self.errors.append("Problem processing mesh, %s." % mesh.name())

    def _smartPrune(self, mesh):
        skin = filter(lambda skin: mesh in skin.getOutputGeometry(), ls(type='skinCluster'))[0]
        vIndex = 0
        for weights in skin.getWeights(mesh.vtx):
            posWeights = [w for w in weights if w > 0]
            posWeights.sort()
            numWeights = len(posWeights)

            ## if number of weights over 3, prune that shit and hope it doesn't fuck up the mesh.
            if numWeights > self.influences:
                culprit = "[" + mesh.vtx[vIndex].split('[')[1]
                print 'In mesh %s, vertex %s has %d weights' % (mesh.name(), culprit, numWeights)
                pruneIndex = (numWeights - self.influences) - 1
                pruneWeight = float("%.03f" % posWeights[pruneIndex]) + 0.001
                culpritVtx = ".vtx[" + mesh.vtx[vIndex].split('[')[1]
                skinPercent(skin, mesh + culpritVtx, pruneWeights=pruneWeight)

            vIndex += 1

    def processBones(self):
        print "Tidying keyframes for the %s skeleton" % self.genderPrefix
        # filter any bones with deleteKeysStr in name and delete all keyframes on those
        # simplify curves with correct thresholds for remaining bones
        bones = self.__jointsList

        if self.options['spin']:
            # get more accurate key values
            # use first bone (it should be the same for all bones else it wont work)
            split = sorted(set(keyframe(bones[0], time = (self.spinKeyStart, self.spinKeyEnd), query = True)))
            print split
            if not len(split):
                print 'No sub-keyframes found from split frame parameter'

            splitKeys = split[1:-1] if len(split) == 4 else split
            self.spinKeyStart = splitKeys[0]
            # self.spinKeyEnd = splitKeys[1]
            print "Spin animation: Rotate flip happens at %s and %s" % (self.spinKeyStart, self.spinKeyEnd)

        for bone in bones:
            bName = bone.name()
            clean = True
            for k in self.deleteKeysStr:
                if k in bName:
                    print "Deleting keyframes on bone, '%s'" % bName
                    self.deleteKeys(bone)
                    clean = False

            if clean:
                print "Cleaning up keyframes on bone, '%s'" % bName
                self.simplifyKeys(bone, spin=self.options['spin'])

    def _removeNamespaces(self, nodes):
        all_ns = [node.namespace() for node in nodes if node.namespace()]
        # remove dupes
        all_ns = list(set(all_ns))
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

    def deleteKeys(self, bone):
        # clear all keys for whole time range
        cutKey(bone, clear=1, time=':', hi='none', shape=1)

    def simplifyKeys(self, bone, spin=False):
        # delete static channels
        delete(bone, staticChannels=1, uac=1, hi='none', shape=1)
        return
        # simplify remaining keys
        tolerance = self.simplifyTolerance
        if 'blink' in bone.name() or 'eye_ball' in bone.name():
            tolerance = self.blinkSimplifyTolerance
        if spin:
            tolerance = self.spinSimplifyTolerance
            # if bone.name() == 'body_hip_bind':
            #     tolerance = 0.03
            firstTimeStr = "%d:%d" % (self.startFrame, self.spinKeyStart)
            secondTimeStr = "%d:%d" % (self.spinKeyEnd, self.endFrame)
            # filterCurve(bone, f='simplify', timeTolerance=tolerance, startTime=self.startFrame, endTime=self.spinKeyStart)
            # filterCurve(bone, f='simplify', timeTolerance=tolerance,  startTime=self.spinKeyEnd, endTime=self.endFrame)
            simplify(bone, time=firstTimeStr, timeTolerance=tolerance, valueTolerance=self.valueTolerance)
            simplify(bone, time=secondTimeStr, timeTolerance=tolerance, valueTolerance=self.valueTolerance)
        else:
            # filterCurve(bone, f='simplify', timeTolerance=tolerance)
            if self.genderPrefix == 'female' and self.options['animationData']['name'] == 'headTurnD':
                if 'blink' in bone.name() or 'eye_ball' in bone.name():
                    filterCurve(bone, f='simplify', timeTolerance=0.02)
                else:
                    filterCurve(bone, f='simplify', timeTolerance=0.08)
            elif self.genderPrefix == 'male' and self.options['animationData']['name'] == 'celiIdleC':
                if 'blink' in bone.name() or 'eye_ball' in bone.name():
                    filterCurve(bone, f='simplify', timeTolerance=0.02)
                else:
                    filterCurve(bone, f='simplify', timeTolerance=0.04)

            else:
                simplify(bone, time=":", timeTolerance=tolerance, valueTolerance=self.valueTolerance)


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

    def _getJoints(self):
        return [j for j in ls(type='joint', v=1)]

    def _exportBones(self):
        joints = self.__jointsList
        if not len(joints):
            self.errors.append("No joints were found. No skeleton exported.")
            return False

        for joint in joints:
            if joint.getParent():
                parentIndex = self._indexOfJoint(joint.getParent().name())
            else:
                parentIndex = -1
            rotq = joint.getRotation(quaternion=True) * joint.getOrientation()
            pos = joint.getTranslation()
            print joint.name()
            self.bones.append({
                "parent": parentIndex,
                "name": '%s_%s' % (self.genderPrefix, joint.name()),
                "pos": self._roundPos(pos),
                "rotq": self._roundQuat(rotq)
            })
            
        return True

    def _indexOfJoint(self, name):
        if not hasattr(self, '_jointNames'):
            self._jointNames = dict([(joint.name(), i) for i, joint in enumerate(self.__jointsList)])

        if name in self._jointNames:
            return self._jointNames[name]
        else:
            return -1

    def _exportSkins(self, mesh):


        print("exporting skins for mesh: " + mesh.name())
        skins = filter(lambda skin: mesh in skin.getOutputGeometry(), ls(type='skinCluster'))

        if len(skins) == 1:
            print("mesh has " + str(len(skins)) + " skins")
            skin = skins[0]
            joints = skin.influenceObjects()
            for weights in skin.getWeights(mesh.vtx):
                numWeights = 0

                for i in range(0, len(weights)):
                    if weights[i] > 0:
                        self.skinWeights.append(weights[i])
                        self.skinIndices.append(self._indexOfJoint(joints[i].name()))
                        numWeights += 1

                if numWeights > self.influences:
                    raise Exception("More than " + str(self.influences) + " influences on a vertex in " + mesh.name() + ".")

                for i in range(0, self.influences - numWeights):
                    self.skinWeights.append(0)
                    self.skinIndices.append(0)
        else:
            print("%s is attached to an incorrect number of skin clusters") % mesh.name()


    def _exportMesh(self, mesh):
        print("Exporting " + mesh.name())
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
            print("Exporting faces")
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
exportPath = "/mnt/NY_Interactive/dev/jack/THREE/assets/models"

undoInfo(openChunk=True)
ThreeJsExporter().run(exportPath, exportOptions)
undoInfo(closeChunk=True)


    

    
    


#for child in selNode.getChildren():
#    fullName = child.longName()
#    splitName = fullName.split('|')
#    tranche = splitName[2]
#    print splitName