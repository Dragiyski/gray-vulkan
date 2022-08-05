#version 460

#define EPSILON (2.220446049250313e-16)

precision highp float;
precision highp int;

layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in;

layout(rgba32f, binding = 0) uniform image2DRect image_screen;

// uniform sampler2D crate_texture;

const float pi = acos(-1.0);

const float negative_infinity = uintBitsToFloat(4286578688u);
const float positive_infinity = uintBitsToFloat(2139095040u);

struct ObjectMatch {
    float distance; // The distance from ray origin to the object;
    vec3 normal; // The normal vector at the intersection;
    vec2 uv; // The uv coordinates;
};

const ObjectMatch no_match = ObjectMatch(
    negative_infinity,
    vec3(0.0, 0.0, 0.0),
    vec2(0.0, 0.0)
);

const ObjectMatch initial_match = ObjectMatch(
    positive_infinity,
    vec3(0.0, 0.0, 0.0),
    vec2(0.0, 0.0)
);

struct Ray {
    vec3 origin;
    vec3 direction;
};

uniform ivec2 screen_size;
uniform vec2 view_size;
uniform vec3 screen_center;
uniform vec3 camera_position;
uniform vec3 camera_up;
uniform vec3 camera_right;

const mat4x3 box_nodes[] = {
    mat4x3(
        vec3(2.0, 0.0, 0.0),
        vec3(0.0, 2.0, 0.0),
        vec3(0.0, 0.0, 2.0),
        vec3(-1.0, -1.0, -1.0)
    ),
    mat4x3(
        vec3(1.0, 0.0, 0.0),
        vec3(0.0, 1.0, 0.0),
        vec3(0.0, 0.0, 1.0),
        vec3(1.0, -0.5, -1.0)
    ),
    mat4x3(
        vec3(0.45276073, 0.19106683, 0.6471247),
        vec3(0.3192436 , -2.1639972 ,  0.41557223),
        vec3(1.1098336 ,  0.01382673, -0.78057736),
        vec3(3.0, 3.0, -1.0)
    ),
    mat4x3(
        vec3(4.148186, 4.603616, 8.752933),
        vec3(-2.1500323,  6.1923585, -2.2379365),
        vec3(-4.5608816, -0.6742422,  2.51611),
        vec3(-3.0, 3.0, -1.0)
    )
};

bool valid_distance(float ray_distance) {
    return !isinf(ray_distance) && !isnan(ray_distance) && ray_distance > 0.0;
}

ObjectMatch object_quad_intersect(Ray ray, mat3 quad_node) {
    ObjectMatch match = ObjectMatch(
        positive_infinity,
        normalize(cross(quad_node[0], quad_node[1])),
        vec2(0.0, 0.0)
    );
    if (dot(match.normal, ray.direction) > 0) {
        match.normal = -match.normal;
    }
    float plane_factor = dot(match.normal, quad_node[2]);
    match.distance = (plane_factor - dot(match.normal, ray.origin)) / dot(match.normal, ray.direction);
    if (!valid_distance(match.distance)) {
        return no_match;
    }
    vec3 point = ray.origin + match.distance * ray.direction;
    match.uv.x = dot(point - quad_node[2], normalize(quad_node[0])) / length(quad_node[0]);
    match.uv.y = dot(point - quad_node[2], normalize(quad_node[1])) / length(quad_node[1]);
    if (match.uv.x >= 0.0 && match.uv.x < 1.0 && match.uv.y >= 0.0 && match.uv.y < 1.0) {
        return match;
    }
    return no_match;
}

ObjectMatch object_box_intersect(Ray ray, mat4x3 box_node) {
    ObjectMatch match = initial_match;
    {
        // Front side
        ObjectMatch quad_match = object_quad_intersect(ray, mat3(box_node[0], box_node[2], box_node[3]));
        if (valid_distance(quad_match.distance) && quad_match.distance < match.distance) {
            match = quad_match;
        }
    }
    {
        // Bottom side
        ObjectMatch quad_match = object_quad_intersect(ray, mat3(box_node[0], -box_node[1], box_node[3] + box_node[1]));
        if (valid_distance(quad_match.distance) && quad_match.distance < match.distance) {
            match = quad_match;
        }
    }
    {
        // Left side
        ObjectMatch quad_match = object_quad_intersect(ray, mat3(-box_node[1], box_node[2], box_node[3] + box_node[1]));
        if (valid_distance(quad_match.distance) && quad_match.distance < match.distance) {
            match = quad_match;
        }
    }
    {
        // Top side
        ObjectMatch quad_match = object_quad_intersect(ray, mat3(box_node[0], box_node[1], box_node[3] + box_node[2]));
        if (valid_distance(quad_match.distance) && quad_match.distance < match.distance) {
            match = quad_match;
        }
    }
    {
        // Back side
        ObjectMatch quad_match = object_quad_intersect(ray, mat3(-box_node[0], box_node[2], box_node[3] + box_node[0] + box_node[1]));
        if (valid_distance(quad_match.distance) && quad_match.distance < match.distance) {
            match = quad_match;
        }
    }
    {
        // Right side
        ObjectMatch quad_match = object_quad_intersect(ray, mat3(box_node[1], box_node[2], box_node[3] + box_node[0]));
        if (valid_distance(quad_match.distance) && quad_match.distance < match.distance) {
            match = quad_match;
        }
    }
    if (valid_distance(match.distance)) {
        return match;
    }
    return no_match;
}

void main() {
    vec2 half_screen = vec2(screen_size) * 0.5;
    vec2 relative_xy = (vec2(gl_WorkGroupID.xy) - half_screen) / half_screen; // [-1; +1] range coordinates
    vec2 rectangle_xy = relative_xy * view_size;
    vec3 rectangle_point = screen_center + rectangle_xy.x * camera_right + rectangle_xy.y * camera_up;
    Ray ray;
    ray.origin = camera_position;
    ray.direction = normalize(rectangle_point - camera_position);

    ObjectMatch match = initial_match;
    
    for (uint i = 0; i < box_nodes.length(); ++i) {
        ObjectMatch object_match = object_box_intersect(ray, box_nodes[i]);
        if (valid_distance(object_match.distance) && object_match.distance < match.distance) {
            match = object_match;
        }
    }

    vec3 color = vec3(0.0);
    if (valid_distance(match.distance)) {
        // color = texture(crate_texture, match.uv).rgb;
        color = match.normal * 0.5 + 0.5;
        // color = vec3(match.uv, 0.0);
    }
    imageStore(image_screen, ivec2(gl_WorkGroupID.xy), vec4(color, 1.0));
}
