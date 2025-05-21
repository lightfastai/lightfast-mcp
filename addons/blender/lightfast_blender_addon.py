# Code created by Siddharth Ahuja: www.github.com/ahujasid © 2025

import io
import json
import socket
import threading
import time
import traceback
from contextlib import redirect_stdout

import bpy
import mathutils
from bpy.props import BoolProperty, IntProperty

bl_info = {
    "name": "Lightfast Blender MCP Addon",
    "author": "Lightfast",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Lightfast MCP",
    "description": "Connect Blender to an MCP client via sockets for core commands.",
    "category": "Interface",
}


class BlenderMCPServer:
    def __init__(self, host="localhost", port=9876):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.server_thread = None

    def start(self):
        if self.running:
            print("Server is already running")
            return
        self.running = True
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            self.server_thread = threading.Thread(target=self._server_loop)
            self.server_thread.daemon = True
            self.server_thread.start()
            print(f"BlenderMCP server started on {self.host}:{self.port}")
        except Exception as e:
            print(f"Failed to start server: {str(e)}")
            self.stop()

    def stop(self):
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:  # noqa E722
                pass
            self.socket = None
        if self.server_thread:
            try:
                if self.server_thread.is_alive():
                    self.server_thread.join(timeout=1.0)
            except:  # noqa E722
                pass
            self.server_thread = None
        print("BlenderMCP server stopped")

    def _server_loop(self):
        print("Server thread started")
        if not self.socket:
            print("Server loop cannot start, socket is not initialized.")
            self.running = False
            return
        self.socket.settimeout(1.0)
        while self.running:
            try:
                try:
                    client, address = self.socket.accept()
                    print(f"Connected to client: {address}")
                    client_thread = threading.Thread(target=self._handle_client, args=(client,))
                    client_thread.daemon = True
                    client_thread.start()
                except TimeoutError:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"Error accepting connection: {str(e)}")
                    time.sleep(0.5)
            except Exception as e:
                if self.running:
                    print(f"Error in server loop: {str(e)}")
                if not self.running:
                    break
                time.sleep(0.5)
        print("Server thread stopped")

    def _handle_client(self, client):
        print("Client handler started")
        client.settimeout(None)
        buffer = b""
        try:
            while self.running:
                try:
                    data = client.recv(8192)
                    if not data:
                        print("Client disconnected")
                        break

                    print(f"Received {len(data)} bytes of data")
                    buffer += data

                    try:
                        # First try to parse as a complete JSON
                        command = json.loads(buffer.decode("utf-8"))
                        buffer = b""  # Clear buffer after successful parse

                        # Process the command
                        def execute_wrapper():
                            response = {"status": "error", "message": "Unknown error occurred"}
                            try:
                                print(f"Processing command: {command.get('type')}")
                                response = self.execute_command(command)
                                print(f"Command processed, response: {str(response)[:100]}...")
                            except Exception as e_exec_cmd:
                                print(f"Error directly in execute_command call: {str(e_exec_cmd)}")
                                traceback.print_exc()
                                response = {"status": "error", "message": str(e_exec_cmd)}
                            finally:
                                try:
                                    response_json = json.dumps(response)
                                    print(f"Sending response ({len(response_json)} bytes)")
                                    client.sendall(response_json.encode("utf-8"))
                                    print("Response sent successfully")
                                except OSError as se_send:
                                    print(f"Failed to send response - socket error: {se_send}")
                                except Exception as e_send_final:
                                    print(f"Failed to send final response: {e_send_final}")
                            return None

                        # For ping command, execute immediately and synchronously
                        if command.get("type") == "ping":
                            print("Handling ping command synchronously")
                            execute_wrapper()
                        else:
                            # Use timer for more complex commands that might need Blender's context
                            print(f"Scheduling {command.get('type')} command for execution")
                            bpy.app.timers.register(execute_wrapper, first_interval=0.0)

                    except json.JSONDecodeError:
                        # If we couldn't parse the entire buffer as JSON, try to find a complete JSON object
                        try:
                            decoded_buffer = buffer.decode("utf-8")
                            json_end = -1
                            open_braces = 0
                            for i, char in enumerate(decoded_buffer):
                                if char == "{":
                                    open_braces += 1
                                elif char == "}":
                                    open_braces -= 1
                                    if open_braces == 0:
                                        json_end = i
                                        break

                            if json_end != -1:
                                # We found a complete JSON object
                                command_str = decoded_buffer[: json_end + 1]
                                command = json.loads(command_str)
                                buffer = decoded_buffer[json_end + 1 :].encode("utf-8")

                                # Process the command
                                def execute_wrapper():
                                    response = {"status": "error", "message": "Unknown error occurred"}
                                    try:
                                        print(f"Processing command: {command.get('type')}")
                                        response = self.execute_command(command)
                                    except Exception as e_exec_cmd:
                                        print(f"Error directly in execute_command call: {str(e_exec_cmd)}")
                                        traceback.print_exc()
                                        response = {"status": "error", "message": str(e_exec_cmd)}
                                    finally:
                                        try:
                                            response_json = json.dumps(response)
                                            print(f"Sending response ({len(response_json)} bytes)")
                                            client.sendall(response_json.encode("utf-8"))
                                            print("Response sent successfully")
                                        except OSError as se_send:
                                            print(f"Failed to send response - socket error: {se_send}")
                                        except Exception as e_send_final:
                                            print(f"Failed to send final response: {e_send_final}")
                                    return None

                                # For ping command, execute immediately and synchronously
                                if command.get("type") == "ping":
                                    print("Handling ping command synchronously")
                                    execute_wrapper()
                                else:
                                    # Use timer for more complex commands that might need Blender's context
                                    print(f"Scheduling {command.get('type')} command for execution")
                                    bpy.app.timers.register(execute_wrapper, first_interval=0.0)
                            else:
                                # If we couldn't find a complete JSON object and the buffer is too large, discard it
                                if len(buffer) > 65536:
                                    print("Buffer too large, discarding.")
                                    buffer = b""
                        except UnicodeDecodeError as ude:
                            print(f"Unicode decode error: {ude}. Clearing buffer.")
                            buffer = b""
                except OSError as se_recv:
                    print(f"Socket error receiving: {se_recv}. Client likely disconnected.")
                    break
                except Exception as e_recv:
                    print(f"Error receiving/processing: {str(e_recv)}")
                    traceback.print_exc()
                    break
        except Exception as e_handler:
            print(f"Error in client handler: {str(e_handler)}")
            traceback.print_exc()
        finally:
            try:
                client.close()
            except:
                pass  # noqa E722
            print("Client handler stopped")

    def execute_command(self, command):
        try:
            print(f"Executing command: {command.get('type')}")
            return self._execute_command_internal(command)
        except Exception as e:
            print(f"Error executing command: {str(e)}")
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def _execute_command_internal(self, command):
        cmd_type = command.get("type")
        params = command.get("params", {})
        handlers = {
            "ping": self.handle_ping,
            "get_scene_info": self.get_scene_info,
            "get_object_info": self.get_object_info,
            "execute_code": self.execute_code,
        }
        handler = handlers.get(cmd_type)
        if handler:
            try:
                print(f"Executing handler for {cmd_type}")
                result = handler(**params)
                print(f"Handler execution complete for {cmd_type}")
                # Make sure the response is properly formatted for network transmission
                response = {"status": "success", "result": result}
                print(f"Prepared response for {cmd_type}: {str(response)[:100]}...")
                return response
            except Exception as e:
                print(f"Error in handler for '{cmd_type}': {str(e)}")
                traceback.print_exc()
                return {"status": "error", "message": str(e)}
        else:
            print(f"Unknown command type received: {cmd_type}")
            return {"status": "error", "message": f"Unknown command type: {cmd_type}"}

    def handle_ping(self, **kwargs):
        print("Handling ping command...")
        # Use a simpler response for ping to minimize JSON parsing issues
        response = {"message": "pong", "timestamp": time.time()}
        print(f"Ping response prepared: {response}")
        return response

    def get_scene_info(self):
        try:
            scene = bpy.context.scene
            scene_info = {
                "name": scene.name,
                "frame_current": scene.frame_current,
                "object_count": len(bpy.data.objects),
                "selected_objects_count": len(bpy.context.selected_objects),
                "active_object_name": bpy.context.active_object.name if bpy.context.active_object else None,
                "render_engine": scene.render.engine,
                "filepath": bpy.data.filepath,
                "objects": [obj.name for obj in bpy.data.objects[:20]],
            }
            return scene_info
        except Exception as e:
            traceback.print_exc()
            raise Exception(f"Error in get_scene_info: {str(e)}")

    @staticmethod
    def _get_aabb(obj):
        if obj.type != "MESH":
            raise TypeError("Object must be a mesh to get AABB")
        if not obj.bound_box:
            print(f"Warning: Object {obj.name} has no bound_box data (perhaps no geometry?).")
            return None
        local_bbox_corners = [mathutils.Vector(corner) for corner in obj.bound_box]
        world_bbox_corners = [obj.matrix_world @ corner for corner in local_bbox_corners]
        min_corner = mathutils.Vector(min(v[i] for v in world_bbox_corners) for i in range(3))
        max_corner = mathutils.Vector(max(v[i] for v in world_bbox_corners) for i in range(3))
        return [[round(c, 4) for c in min_corner], [round(c, 4) for c in max_corner]]

    def get_object_info(self, name):
        obj = bpy.data.objects.get(name)
        if not obj:
            raise ValueError(f"Object not found: {name}")
        obj_info = {
            "name": obj.name,
            "type": obj.type,
            "location": [round(c, 4) for c in obj.location],
            "rotation_euler": [round(c, 4) for c in obj.rotation_euler],
            "scale": [round(c, 4) for c in obj.scale],
            "is_visible_viewport": obj.visible_get(),
            "is_visible_render": obj.hide_render is False,
            "parent_name": obj.parent.name if obj.parent else None,
            "children_count": len(obj.children),
            "modifier_count": len(obj.modifiers),
            "material_names": [ms.material.name for ms in obj.material_slots if ms.material],
        }
        if obj.type == "MESH":
            try:
                obj_info["world_bounding_box"] = self._get_aabb(obj)
            except TypeError as te:
                print(f"AABB TypeError for {name}: {te}")
                obj_info["world_bounding_box"] = None
            if obj.data:
                obj_info["mesh_vertices"] = len(obj.data.vertices)
                obj_info["mesh_polygons"] = len(obj.data.polygons)
        return obj_info

    def execute_code(self, code):
        try:
            namespace = {"bpy": bpy, "mathutils": mathutils, "bmesh": None}
            capture_buffer = io.StringIO()
            with redirect_stdout(capture_buffer):
                exec(code, namespace)
            captured_output = capture_buffer.getvalue()
            return {"executed": True, "result": captured_output or "No output."}
        except Exception as e:
            traceback.print_exc()
            raise Exception(f"Code execution error: {str(e)}\nTraceback:\n{traceback.format_exc()}")


class BLENDERMCP_PT_Panel(bpy.types.Panel):
    bl_label = "Lightfast MCP"
    bl_idname = "LIGHTFASTMCP_PT_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lightfast MCP"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.prop(scene, "lightfast_mcp_port", text="Server Port")
        row = layout.row()
        if not scene.lightfast_mcp_server_running:
            row.operator("lightfast_mcp.start_server", text="Start MCP Server", icon="PLAY")
        else:
            row.operator("lightfast_mcp.stop_server", text="Stop MCP Server", icon="PAUSE")
            server_instance = getattr(bpy.types, "lightfast_mcp_server_instance", None)
            if server_instance and server_instance.running:
                layout.label(text=f"Server active on port {server_instance.port}", icon="RADIOBUT_ON")
            else:
                layout.label(text="Server inactive", icon="RADIOBUT_OFF")


class LIGHTFASTMCP_OT_StartServer(bpy.types.Operator):
    bl_idname = "lightfast_mcp.start_server"
    bl_label = "Start Lightfast MCP Server"
    bl_description = "Start the socket server for Lightfast MCP client connections"

    def execute(self, context):
        scene = context.scene
        if not hasattr(bpy.types, "lightfast_mcp_server_instance") or bpy.types.lightfast_mcp_server_instance is None:
            bpy.types.lightfast_mcp_server_instance = BlenderMCPServer(port=scene.lightfast_mcp_port)

        server_instance = bpy.types.lightfast_mcp_server_instance
        if not server_instance.running:
            server_instance.port = scene.lightfast_mcp_port
            server_instance.start()
            if server_instance.running:
                scene.lightfast_mcp_server_running = True
                self.report({"INFO"}, f"Lightfast MCP server started on port {server_instance.port}")
            else:
                scene.lightfast_mcp_server_running = False
                self.report({"ERROR"}, "Failed to start Lightfast MCP server.")
        else:
            self.report({"WARNING"}, "Lightfast MCP server is already running.")
        return {"FINISHED"}


class LIGHTFASTMCP_OT_StopServer(bpy.types.Operator):
    bl_idname = "lightfast_mcp.stop_server"
    bl_label = "Stop Lightfast MCP Server"
    bl_description = "Stop the Lightfast MCP socket server"

    def execute(self, context):
        scene = context.scene
        server_instance = getattr(bpy.types, "lightfast_mcp_server_instance", None)
        if server_instance is not None:
            server_instance.stop()
            self.report({"INFO"}, "Lightfast MCP server stopped.")
        else:
            self.report({"WARNING"}, "Lightfast MCP server not found or not running.")
        scene.lightfast_mcp_server_running = False
        return {"FINISHED"}


_classes = [
    BLENDERMCP_PT_Panel,
    LIGHTFASTMCP_OT_StartServer,
    LIGHTFASTMCP_OT_StopServer,
]


def register():
    bpy.types.Scene.lightfast_mcp_port = IntProperty(name="Server Port", default=9876, min=1024, max=65535)
    bpy.types.Scene.lightfast_mcp_server_running = BoolProperty(default=False)

    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.lightfast_mcp_server_instance = None
    print("Lightfast Blender MCP Addon Registered")


def unregister():
    server_instance = getattr(bpy.types, "lightfast_mcp_server_instance", None)
    if server_instance is not None:
        if server_instance.running:
            server_instance.stop()
        del bpy.types.lightfast_mcp_server_instance

    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.lightfast_mcp_port
    del bpy.types.Scene.lightfast_mcp_server_running
    print("Lightfast Blender MCP Addon Unregistered")


if __name__ == "__main__":
    try:
        unregister()
    except Exception:
        pass
    register()
