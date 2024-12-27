import request from '../utils/request';

export const login = (data) => {
  return request({
    url: '/token',
    method: 'post',
    data: {
      username: data.username,
      password: data.password,
    },
  });
};

export const register = (data) => {
  return request({
    url: '/users/register',
    method: 'post',
    data,
  });
};

export const getUserList = (params) => {
  return request({
    url: '/users',
    method: 'get',
    params,
  });
};


export const updateUser = (id, data) => {
  return request({
    url: `/users/${id}`,
    method: 'put',
    data,
  });
};

export const deleteUser = (id) => {
  return request({
    url: `/users/${id}`,
    method: 'delete',
  });
};
