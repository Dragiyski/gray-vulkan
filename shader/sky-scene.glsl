#version 460

#define EPSILON (2.220446049250313e-16)

precision highp float;
precision highp int;

layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in;

layout(rgba32f, binding = 0) uniform image2DRect image_ray_direction;

const vec3 color_sky = vec3(0.09, 0.626, 0.9);
const vec3 color_sky_horizon = vec3(0.34, 0.68, 0.85);
const vec3 color_ground_horizon = vec3(0.75, 0.75, 0.75);
const vec3 color_ground = vec3(0.5, 0.5, 0.5);
const float size_horizon = 0.2;

layout(push_constant, std430) uniform CameraBlock {
    uniform vec2 view_size;
    uniform vec3 screen_center;
    uniform vec3 camera_position;
    uniform vec3 camera_up;
    uniform vec3 camera_right;
};

void main() {
    vec2 half_screen = vec2(gl_NumWorkGroups.xy) * 0.5;
    vec2 relative_xy = (vec2(gl_WorkGroupID.xy) - half_screen) / half_screen; // [-1; +1] range coordinates
    vec2 rectangle_xy = relative_xy * view_size;
    vec3 rectangle_point = screen_center + rectangle_xy.x * camera_right + rectangle_xy.y * camera_up;
    vec3 ray_direction = normalize(rectangle_point - camera_position);
    float sky_z = ray_direction.z; // 1.0 = sky, -1.0 = ground, 0.0 = horizon
    float cm = 1.0;
    if (abs(ray_direction.x) >= EPSILON) {
        float direction_xy = atan(ray_direction.x, ray_direction.y);
        cm = 1.0 - abs(direction_xy) / acos(-1.0);
    }
    vec3 color;
    if (sky_z >= size_horizon) {
        float nuance = (sky_z - size_horizon) / (1.0 - size_horizon);
        color = nuance * color_sky + (1.0 - nuance) * color_sky_horizon;
    } else if (sky_z <= -size_horizon) {
        float nuance = ((-sky_z - size_horizon) / (1.0 - size_horizon));
        color = nuance * color_ground + (1.0 - nuance) * color_ground_horizon;
    } else {
        float nuance = (sky_z + size_horizon) / (2 * size_horizon);
        color = (nuance) * color_sky_horizon + (1.0 - nuance) * color_ground_horizon;
    }
    imageStore(image_ray_direction, ivec2(gl_WorkGroupID.xy), vec4(cm * color, 1.0));
}
